"""Configurable Agent workflow routes."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import require_login
from backend.app.core.db import get_connection
from backend.app.core.runtime_config import sandbox_tool_disabled
from backend.app.services.tools import test_tool
from cli.tools.sandbox import execute_python

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

SUPPORTED_NODE_TYPES = {"Planner", "Researcher", "Coder", "Reporter", "Artifact", "Human Feedback", "MCP Tool"}


class WorkflowRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)


class RunWorkflowRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


@router.get("")
async def list_workflows(user: dict = Depends(require_login)):
    conn = get_connection()
    rows = conn.execute(
        """SELECT workflow_id, user_id, name, description, nodes_json, edges_json, budget_json, created_at, updated_at
           FROM workflows
           WHERE user_id = ?
           ORDER BY updated_at DESC""",
        (user["user_id"],),
    ).fetchall()
    conn.close()
    return [_public_workflow(dict(row)) for row in rows]


@router.post("", status_code=201)
async def create_workflow(req: WorkflowRequest, user: dict = Depends(require_login)):
    _validate_nodes(req.nodes)
    workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO workflows
           (workflow_id, user_id, name, description, nodes_json, edges_json, budget_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            workflow_id,
            user["user_id"],
            req.name,
            req.description,
            json.dumps(req.nodes, ensure_ascii=False),
            json.dumps(req.edges, ensure_ascii=False),
            json.dumps(req.budget, ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)).fetchone()
    conn.close()
    return _public_workflow(dict(row))


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, user: dict = Depends(require_login)):
    workflow = _get_workflow(workflow_id, user["user_id"])
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _public_workflow(workflow)


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, req: WorkflowRequest, user: dict = Depends(require_login)):
    if not _get_workflow(workflow_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Workflow not found")
    _validate_nodes(req.nodes)
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """UPDATE workflows
           SET name = ?, description = ?, nodes_json = ?, edges_json = ?, budget_json = ?, updated_at = ?
           WHERE workflow_id = ? AND user_id = ?""",
        (
            req.name,
            req.description,
            json.dumps(req.nodes, ensure_ascii=False),
            json.dumps(req.edges, ensure_ascii=False),
            json.dumps(req.budget, ensure_ascii=False),
            now,
            workflow_id,
            user["user_id"],
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)).fetchone()
    conn.close()
    return _public_workflow(dict(row))


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, user: dict = Depends(require_login)):
    conn = get_connection()
    cur = conn.execute("DELETE FROM workflows WHERE workflow_id = ? AND user_id = ?", (workflow_id, user["user_id"]))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"deleted": True, "workflow_id": workflow_id}


@router.post("/{workflow_id}/runs", status_code=201)
async def run_workflow(workflow_id: str, req: RunWorkflowRequest, user: dict = Depends(require_login)):
    workflow = _get_workflow(workflow_id, user["user_id"])
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    run_id = f"wfr_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO workflow_runs
           (run_id, workflow_id, user_id, status, input_json, outputs_json, error, created_at, updated_at)
           VALUES (?, ?, ?, 'running', ?, '{}', '', ?, ?)""",
        (run_id, workflow_id, user["user_id"], json.dumps(req.input, ensure_ascii=False), now, now),
    )
    conn.commit()
    conn.close()

    outputs: dict[str, Any] = {}
    trace: list[dict[str, Any]] = []
    status = "completed"
    error = ""
    try:
        nodes = json.loads(workflow["nodes_json"] or "[]")
        budget = json.loads(workflow["budget_json"] or "{}")
        max_steps = int(budget.get("max_steps") or len(nodes) or 1)
        for index, node in enumerate(nodes[:max_steps]):
            node_result = await _run_node(node, req.input, outputs, user, workflow_id, run_id)
            outputs[node_result["node_id"]] = node_result["output"]
            trace.append(node_result)
            if node_result["status"] == "failed":
                retries = int(node.get("retry") or budget.get("retries") or 0)
                if retries > 0:
                    retry_result = await _run_node(node, req.input, outputs, user, workflow_id, run_id, attempt=2)
                    outputs[f"{node_result['node_id']}:retry"] = retry_result["output"]
                    trace.append(retry_result)
                    if retry_result["status"] == "completed":
                        continue
                status = "failed"
                error = node_result.get("error", "")
                break
    except Exception as exc:
        status = "failed"
        error = str(exc)

    final = {"outputs": outputs, "trace": trace}
    conn = get_connection()
    conn.execute(
        """UPDATE workflow_runs SET status = ?, outputs_json = ?, error = ?, updated_at = ?
           WHERE run_id = ? AND user_id = ?""",
        (status, json.dumps(final, ensure_ascii=False), error[:2000], datetime.now().isoformat(), run_id, user["user_id"]),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    return _public_run(dict(row))


@router.get("/{workflow_id}/runs")
async def list_workflow_runs(workflow_id: str, user: dict = Depends(require_login)):
    if not _get_workflow(workflow_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Workflow not found")
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM workflow_runs
           WHERE workflow_id = ? AND user_id = ?
           ORDER BY created_at DESC""",
        (workflow_id, user["user_id"]),
    ).fetchall()
    conn.close()
    return [_public_run(dict(row)) for row in rows]


@router.get("/runs/{run_id}/trace")
async def get_workflow_trace(run_id: str, user: dict = Depends(require_login)):
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM workflow_node_runs
           WHERE run_id = ? AND user_id = ?
           ORDER BY created_at ASC""",
        (run_id, user["user_id"]),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def _run_node(
    node: dict[str, Any],
    workflow_input: dict[str, Any],
    outputs: dict[str, Any],
    user: dict,
    workflow_id: str,
    run_id: str,
    attempt: int = 1,
) -> dict[str, Any]:
    started = time.perf_counter()
    node_id = str(node.get("id") or f"node_{uuid.uuid4().hex[:8]}")
    node_type = str(node.get("type") or "")
    config = node.get("config") or {}
    input_summary = f"attempt={attempt}; keys={','.join(workflow_input.keys())}; prior_nodes={len(outputs)}"
    status = "completed"
    error = ""
    tool_calls: list[dict[str, Any]] = []
    try:
        if node_type == "Planner":
            output = {"plan": config.get("plan") or ["clarify", "research", "report"], "topic": workflow_input.get("topic", "")}
        elif node_type == "Researcher":
            output = {"summary": config.get("summary") or f"Research node received topic: {workflow_input.get('topic', '')}"}
        elif node_type == "Coder":
            if sandbox_tool_disabled():
                status = "failed"
                error = "Python sandbox is disabled for this demo"
                output = {"stdout": "", "stderr": error, "success": False}
                tool_calls.append({"tool": "python_sandbox", "elapsed_seconds": 0, "success": False})
            else:
                code = str(config.get("code") or workflow_input.get("code") or "print('DeepFlow workflow coder node')")
                result = await execute_python(code, timeout=int(config.get("timeout") or 10))
                output = {"stdout": result.stdout, "stderr": result.stderr, "success": result.success}
                if not result.success:
                    status = "failed"
                    error = result.error or result.stderr
                tool_calls.append({"tool": "python_sandbox", "elapsed_seconds": result.elapsed_seconds, "success": result.success})
        elif node_type == "Reporter":
            output = {"markdown": config.get("markdown") or _compose_report(workflow_input, outputs)}
        elif node_type == "Artifact":
            output = {"artifact_type": config.get("artifact_type", "markdown"), "content": config.get("content") or json.dumps(outputs, ensure_ascii=False)}
        elif node_type == "Human Feedback":
            output = {"pending": bool(config.get("pause", False)), "instruction": config.get("instruction", "")}
        elif node_type == "MCP Tool":
            tool_id = str(config.get("tool_id") or "")
            tool_input = config.get("input") or workflow_input
            result = await test_tool(tool_id, tool_input, user)
            output = result
            if not result.get("success"):
                status = "failed"
                error = result.get("error", "")
            tool_calls.append({"tool": tool_id, "elapsed_seconds": result.get("elapsed_seconds", 0), "success": result.get("success")})
        else:
            status = "failed"
            error = f"Unsupported node type: {node_type}"
            output = {}
    except Exception as exc:
        status = "failed"
        error = str(exc)
        output = {}

    elapsed = time.perf_counter() - started
    output_summary = json.dumps(output, ensure_ascii=False)[:1000]
    _save_node_trace(
        run_id=run_id,
        workflow_id=workflow_id,
        user_id=user["user_id"],
        node_id=node_id,
        node_type=node_type,
        status=status,
        input_summary=input_summary,
        output_summary=output_summary,
        tool_calls=tool_calls,
        elapsed_seconds=elapsed,
        error=error,
    )
    return {
        "node_id": node_id,
        "node_type": node_type,
        "status": status,
        "output": output,
        "error": error,
        "elapsed_seconds": round(elapsed, 3),
    }


def _save_node_trace(
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
    conn = get_connection()
    conn.execute(
        """INSERT INTO workflow_node_runs
           (node_run_id, run_id, workflow_id, user_id, node_id, node_type, status,
            input_summary, output_summary, tool_calls_json, elapsed_seconds, error, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            f"wfn_{uuid.uuid4().hex[:12]}",
            run_id,
            workflow_id,
            user_id,
            node_id,
            node_type,
            status,
            input_summary[:2000],
            output_summary[:4000],
            json.dumps(tool_calls, ensure_ascii=False),
            elapsed_seconds,
            error[:2000],
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def _get_workflow(workflow_id: str, user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM workflows WHERE workflow_id = ? AND user_id = ?",
        (workflow_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _validate_nodes(nodes: list[dict[str, Any]]) -> None:
    for node in nodes:
        node_type = str(node.get("type") or "")
        if node_type not in SUPPORTED_NODE_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported workflow node type: {node_type}")


def _public_workflow(row: dict) -> dict:
    return {
        "workflow_id": row["workflow_id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "description": row["description"],
        "nodes": json.loads(row.get("nodes_json") or "[]"),
        "edges": json.loads(row.get("edges_json") or "[]"),
        "budget": json.loads(row.get("budget_json") or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _public_run(row: dict) -> dict:
    return {
        "run_id": row["run_id"],
        "workflow_id": row["workflow_id"],
        "user_id": row["user_id"],
        "status": row["status"],
        "input": json.loads(row.get("input_json") or "{}"),
        "outputs": json.loads(row.get("outputs_json") or "{}"),
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _compose_report(workflow_input: dict[str, Any], outputs: dict[str, Any]) -> str:
    topic = workflow_input.get("topic") or "Workflow Report"
    return f"# {topic}\n\n## Workflow Outputs\n\n```json\n{json.dumps(outputs, ensure_ascii=False, indent=2)}\n```\n"
