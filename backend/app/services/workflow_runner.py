"""Sequential workflow execution with persistent, resumable checkpoints."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any

from backend.app.repositories.workflow import save_node_run
from backend.app.core.runtime_config import sandbox_tool_disabled
from backend.app.services.tools import test_tool
from cli.agents.planner import generate_plan
from cli.agents.reporter import generate_report
from cli.agents.researcher import research_step
from cli.models import ResearchFinding, ResearchPlan
from cli.tools.sandbox import execute_python

SUPPORTED_NODE_TYPES = {
    "Planner",
    "Researcher",
    "Coder",
    "Reporter",
    "Artifact",
    "Human Feedback",
    "MCP Tool",
}


async def execute_workflow(
    *,
    nodes: list[dict[str, Any]],
    workflow_input: dict[str, Any],
    user: dict[str, Any],
    workflow_id: str,
    run_id: str,
    budget: dict[str, Any] | None = None,
    checkpoint: dict[str, Any] | None = None,
    start_index: int = 0,
) -> dict[str, Any]:
    """Execute configured nodes in list order and return a serializable checkpoint."""
    budget = budget or {}
    state = _normalize_checkpoint(checkpoint)
    outputs: dict[str, Any] = state["outputs"]
    trace: list[dict[str, Any]] = state["trace"]
    token_usage = int(state["token_usage"])
    max_steps = max(1, int(budget.get("max_steps") or len(nodes) or 1))
    max_tokens = max(0, int(budget.get("max_tokens") or budget.get("max_tokens_budget") or 0))
    executable_nodes = nodes[:max_steps]

    for index in range(start_index, len(executable_nodes)):
        node = executable_nodes[index]
        retries = max(0, int(node.get("retry") or budget.get("retries") or 0))
        result: dict[str, Any] | None = None

        for attempt in range(1, retries + 2):
            result = await _run_node(
                node=node,
                workflow_input=workflow_input,
                outputs=outputs,
                user=user,
                workflow_id=workflow_id,
                run_id=run_id,
                attempt=attempt,
            )
            trace.append(result)
            output_key = result["node_id"] if attempt == 1 else f"{result['node_id']}:retry:{attempt}"
            outputs[output_key] = result["output"]
            token_usage += int(result.get("token_usage") or 0)

            if result["status"] in {"completed", "waiting_feedback"}:
                break

        if result is None:
            continue
        if result["status"] == "waiting_feedback":
            return _checkpoint(
                status="waiting_feedback",
                outputs=outputs,
                trace=trace,
                next_node_index=index + 1,
                token_usage=token_usage,
                waiting_node_id=result["node_id"],
                feedback=state["feedback"],
            )
        if result["status"] != "completed":
            return _checkpoint(
                status="failed",
                outputs=outputs,
                trace=trace,
                next_node_index=index,
                token_usage=token_usage,
                error=result.get("error", ""),
                feedback=state["feedback"],
            )
        if max_tokens and token_usage > max_tokens:
            return _checkpoint(
                status="failed",
                outputs=outputs,
                trace=trace,
                next_node_index=index + 1,
                token_usage=token_usage,
                error=f"Workflow token budget exceeded: {token_usage}/{max_tokens}",
                feedback=state["feedback"],
            )

    if len(nodes) > max_steps:
        return _checkpoint(
            status="failed",
            outputs=outputs,
            trace=trace,
            next_node_index=len(executable_nodes),
            token_usage=token_usage,
            error=f"Workflow step budget exceeded: {len(nodes)}/{max_steps}",
            feedback=state["feedback"],
        )

    return _checkpoint(
        status="completed",
        outputs=outputs,
        trace=trace,
        next_node_index=len(executable_nodes),
        token_usage=token_usage,
        feedback=state["feedback"],
    )


def apply_feedback(checkpoint: dict[str, Any], feedback: Any) -> dict[str, Any]:
    """Attach human feedback to the paused node before continuing."""
    state = _normalize_checkpoint(checkpoint)
    waiting_node_id = str(state.get("waiting_node_id") or "")
    if not waiting_node_id:
        raise ValueError("Workflow run has no pending Human Feedback node")
    pending_output = state["outputs"].get(waiting_node_id)
    if not isinstance(pending_output, dict):
        pending_output = {}
    pending_output.update({"pending": False, "feedback": feedback})
    state["outputs"][waiting_node_id] = pending_output
    state["feedback"].append({"node_id": waiting_node_id, "value": feedback})
    state["waiting_node_id"] = ""
    return state


async def _run_node(
    *,
    node: dict[str, Any],
    workflow_input: dict[str, Any],
    outputs: dict[str, Any],
    user: dict[str, Any],
    workflow_id: str,
    run_id: str,
    attempt: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    node_id = str(node.get("id") or f"node_{uuid.uuid4().hex[:8]}")
    node_type = str(node.get("type") or "")
    config = node.get("config") or {}
    status = "completed"
    error = ""
    token_usage = 0
    tool_calls: list[dict[str, Any]] = []
    feedback_context = _feedback_text(workflow_input.get("human_feedback"))

    try:
        if node_type == "Planner":
            topic = str(config.get("topic") or workflow_input.get("topic") or "").strip()
            if not topic:
                raise ValueError("Planner requires workflow input 'topic'")
            locale = str(config.get("locale") or workflow_input.get("locale") or "zh-CN")
            plan, prompt_tokens, completion_tokens = await generate_plan(
                topic=topic,
                locale=locale,
                max_steps=max(1, int(config.get("max_steps") or 5)),
                context=_join_context(
                    str(config.get("context") or workflow_input.get("context") or ""),
                    feedback_context,
                ),
            )
            token_usage = prompt_tokens + completion_tokens
            output = {
                "plan": plan.model_dump(mode="json"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        elif node_type == "Researcher":
            plan = _resolve_plan(config, workflow_input, outputs)
            locale = str(config.get("locale") or workflow_input.get("locale") or plan.locale)
            requested_index = config.get("step_index")
            selected_steps = (
                [(int(requested_index), plan.steps[int(requested_index) - 1])]
                if requested_index is not None
                else list(enumerate(plan.steps, 1))
            )
            findings: list[ResearchFinding] = []
            prompt_tokens = 0
            completion_tokens = 0
            for step_index, step in selected_steps:
                if feedback_context:
                    step = step.model_copy(
                        update={
                            "description": _join_context(
                                step.description,
                                f"Human feedback: {feedback_context}",
                            )
                        }
                    )
                finding, pt, ct = await research_step(
                    step=step,
                    step_index=step_index,
                    total_steps=len(plan.steps),
                    locale=locale,
                    search_domains=config.get("search_domains") or workflow_input.get("search_domains"),
                    recency_days=config.get("recency_days") or workflow_input.get("recency_days"),
                )
                findings.append(finding)
                prompt_tokens += pt
                completion_tokens += ct
            token_usage = prompt_tokens + completion_tokens
            output = {
                "findings": [item.model_dump(mode="json") for item in findings],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        elif node_type == "Reporter":
            plan = _resolve_plan(config, workflow_input, outputs)
            findings = _resolve_findings(config, workflow_input, outputs)
            if feedback_context:
                findings.append(
                    ResearchFinding(
                        step_id="human_feedback",
                        step_title="Human feedback",
                        problem_statement="Apply the user's feedback to the final report.",
                        findings_markdown=feedback_context,
                        conclusion="The final report must reflect this feedback.",
                        references=[],
                    )
                )
            markdown, prompt_tokens, completion_tokens = await generate_report(
                plan=plan,
                findings=findings,
                locale=str(config.get("locale") or workflow_input.get("locale") or plan.locale),
                report_style=str(config.get("report_style") or workflow_input.get("report_style") or "general"),
            )
            token_usage = prompt_tokens + completion_tokens
            output = {
                "markdown": markdown,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        elif node_type == "Coder":
            if sandbox_tool_disabled():
                raise RuntimeError("Python sandbox is disabled")
            code = str(config.get("code") or workflow_input.get("code") or "").strip()
            if not code:
                raise ValueError("Coder requires Python code")
            result = await execute_python(code, timeout=max(1, int(config.get("timeout") or 10)))
            output = {"stdout": result.stdout, "stderr": result.stderr, "success": result.success}
            tool_calls.append(
                {
                    "tool": "python_sandbox",
                    "elapsed_seconds": result.elapsed_seconds,
                    "success": result.success,
                }
            )
            if not result.success:
                raise RuntimeError(result.error or result.stderr or "Python execution failed")
        elif node_type == "Artifact":
            output = {
                "artifact_type": str(config.get("artifact_type") or "markdown"),
                "content": config.get("content") or _latest_report(outputs),
            }
        elif node_type == "Human Feedback":
            pause = bool(config.get("pause", False))
            status = "waiting_feedback" if pause else "completed"
            output = {
                "pending": pause,
                "instruction": str(config.get("instruction") or ""),
            }
        elif node_type == "MCP Tool":
            tool_id = str(config.get("tool_id") or "")
            if not tool_id:
                raise ValueError("MCP Tool requires config.tool_id")
            result = await test_tool(tool_id, config.get("input") or workflow_input, user)
            output = result
            tool_calls.append(
                {
                    "tool": tool_id,
                    "elapsed_seconds": result.get("elapsed_seconds", 0),
                    "success": result.get("success", False),
                }
            )
            if not result.get("success"):
                raise RuntimeError(str(result.get("error") or "Tool call failed"))
        else:
            raise ValueError(f"Unsupported node type: {node_type}")
    except Exception as exc:
        status = "failed"
        error = str(exc)
        output = {}

    elapsed = time.perf_counter() - started
    result = {
        "node_id": node_id,
        "node_type": node_type,
        "status": status,
        "attempt": attempt,
        "output": output,
        "error": error,
        "elapsed_seconds": round(elapsed, 3),
        "token_usage": token_usage,
    }
    _save_node_trace(
        run_id=run_id,
        workflow_id=workflow_id,
        user_id=str(user["user_id"]),
        node_id=node_id,
        node_type=node_type,
        status=status,
        input_summary=(
            f"attempt={attempt}; keys={','.join(workflow_input.keys())}; "
            f"prior_nodes={len(outputs)}"
        ),
        output_summary=json.dumps(output, ensure_ascii=False, default=str)[:4000],
        tool_calls=tool_calls,
        elapsed_seconds=elapsed,
        error=error,
    )
    return result


def _feedback_text(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False)


def _join_context(*parts: str) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _resolve_plan(
    config: dict[str, Any],
    workflow_input: dict[str, Any],
    outputs: dict[str, Any],
) -> ResearchPlan:
    raw_plan = config.get("plan") or workflow_input.get("plan")
    if raw_plan:
        return ResearchPlan.model_validate(raw_plan)
    for value in reversed(list(outputs.values())):
        if isinstance(value, dict) and value.get("plan"):
            return ResearchPlan.model_validate(value["plan"])
    raise ValueError("Node requires a completed Planner output")


def _resolve_findings(
    config: dict[str, Any],
    workflow_input: dict[str, Any],
    outputs: dict[str, Any],
) -> list[ResearchFinding]:
    raw_findings = config.get("findings") or workflow_input.get("findings")
    if raw_findings:
        return [ResearchFinding.model_validate(item) for item in raw_findings]
    for value in reversed(list(outputs.values())):
        if isinstance(value, dict) and value.get("findings"):
            return [ResearchFinding.model_validate(item) for item in value["findings"]]
    raise ValueError("Reporter requires a completed Researcher output")


def _latest_report(outputs: dict[str, Any]) -> str:
    for value in reversed(list(outputs.values())):
        if isinstance(value, dict) and isinstance(value.get("markdown"), str):
            return value["markdown"]
    return json.dumps(outputs, ensure_ascii=False, indent=2, default=str)


def _normalize_checkpoint(checkpoint: dict[str, Any] | None) -> dict[str, Any]:
    checkpoint = checkpoint or {}
    return {
        "outputs": dict(checkpoint.get("outputs") or {}),
        "trace": list(checkpoint.get("trace") or []),
        "next_node_index": max(0, int(checkpoint.get("next_node_index") or 0)),
        "token_usage": max(0, int(checkpoint.get("token_usage") or 0)),
        "waiting_node_id": str(checkpoint.get("waiting_node_id") or ""),
        "feedback": list(checkpoint.get("feedback") or []),
        "execution_mode": "sequential",
        "edges_applied": False,
    }


def _checkpoint(
    *,
    status: str,
    outputs: dict[str, Any],
    trace: list[dict[str, Any]],
    next_node_index: int,
    token_usage: int,
    error: str = "",
    waiting_node_id: str = "",
    feedback: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "outputs": outputs,
        "trace": trace,
        "next_node_index": next_node_index,
        "token_usage": token_usage,
        "waiting_node_id": waiting_node_id,
        "feedback": list(feedback or []),
        "execution_mode": "sequential",
        "edges_applied": False,
        "error": error,
    }


def _save_node_trace(
    *,
    run_id: str,
    workflow_id: str,
    user_id: str,
    node_id: str,
    node_type: str,
    status: str,
    input_summary: str,
    output_summary: str,
    tool_calls: list[dict[str, Any]],
    elapsed_seconds: float,
    error: str,
) -> None:
    save_node_run(
        {
            "node_run_id": f"wfn_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "workflow_id": workflow_id,
            "user_id": user_id,
            "node_id": node_id,
            "node_type": node_type,
            "status": status,
            "input_summary": input_summary[:2000],
            "output_summary": output_summary[:4000],
            "tool_calls": tool_calls,
            "elapsed_seconds": elapsed_seconds,
            "error": error[:2000],
            "created_at": datetime.now().isoformat(),
        }
    )
