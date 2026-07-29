"""
研究任务服务 — 后台异步执行研究流程

复用 CLI 的 Agent 和状态机，封装为 FastAPI 后台任务。
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 path 中
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from cli.config import Config
from cli.budget import budget_from_task
from cli.pricing import PRICING_VERSION, estimate_cost_rmb
from cli.models import ResearchPlan, ResearchFinding, SourceReference, SourceType
from cli.agents.planner import generate_plan
from cli.agents.researcher import research_step
from cli.agents.coder import process_step
from cli.agents.reporter import generate_report
from backend.app.repositories.research import (
    update_task,
    save_step,
    update_step,
    get_task,
    list_steps,
    save_agent_run,
)
from backend.app.core.events import get_event_manager, remove_event_manager
from backend.app.services.embedding import EmbeddingError
from backend.app.services.knowledge import search_knowledge_chunks
from backend.app.core.runtime_config import sandbox_tool_disabled
from backend.app.core.errors import classify_failure

logger = logging.getLogger("deepflow.backend")


async def generate_research_plan_task(
    task_id: str,
    topic: str,
    locale: str = "zh-CN",
    max_steps: int | None = None,
):
    """后台生成研究计划，等待用户确认后再执行。"""
    emitter = get_event_manager(task_id)
    started_at = time.time()
    task = get_task(task_id) or {}
    budget = budget_from_task(task)

    try:
        await emitter.emit("coordinator.started", task_id=task_id)
        update_task(task_id, status="planning")

        phase_started = time.time()
        _ensure_call_capacity(0, 2048, budget.max_tokens)
        planner_model = task.get("planner_model") or Config.PLANNER_MODEL
        plan, pt, ct = await generate_plan(
            topic=topic,
            locale=locale,
            max_steps=max_steps or Config.MAX_STEPS,
            model_override=planner_model,
        )
        save_agent_run(
            task_id=task_id,
            agent_name="Planner",
            phase="planning",
            status="completed",
            input_summary=topic,
            output_summary=f"{plan.title}\n" + "\n".join(f"- {s.title}" for s in plan.steps),
            prompt_tokens=pt,
            completion_tokens=ct,
            elapsed_seconds=time.time() - phase_started,
        )
        _ensure_token_budget(pt + ct, budget.max_tokens)

        plan_dict = plan.model_dump()
        update_task(
            task_id,
            status="awaiting_confirmation",
            plan_json=json.dumps(plan_dict, ensure_ascii=False),
            total_steps=len(plan.steps),
            prompt_tokens=pt,
            completion_tokens=ct,
            tokens_used=pt + ct,
            cost_rmb=estimate_cost_rmb(planner_model, pt, ct),
            pricing_version=task.get("pricing_version") or PRICING_VERSION,
            elapsed_seconds=time.time() - started_at,
        )

        for i, step in enumerate(plan.steps):
            save_step(task_id, i + 1, step.title, step.description, step.need_search)

        await emitter.emit(
            "planner.completed",
            plan=plan_dict,
            steps_count=len(plan.steps),
        )

    except Exception as e:
        failure = classify_failure(e)
        logger.exception(
            "研究计划生成失败",
            extra={
                "task_id": task_id,
                "user_id": task.get("user_id"),
                "phase": "planning",
                "elapsed": round(time.time() - started_at, 3),
                "error_code": failure.code,
            },
        )
        raise


async def execute_research_task(task_id: str):
    """
    后台执行已经确认的研究计划。
    每个阶段都通过 EventManager 推送进度事件。
    """
    emitter = get_event_manager(task_id)
    total_prompt = 0
    total_completion = 0
    total_search_calls = 0
    total_crawl_calls = 0
    total_search_credits = 0
    started_at = time.time()
    task: dict = {}

    try:
        task = get_task(task_id)
        if task is None:
            raise RuntimeError("任务不存在")
        if not task.get("plan_json"):
            raise RuntimeError("研究计划不存在，无法执行")

        locale = task["locale"]
        plan = ResearchPlan.model_validate_json(task["plan_json"])
        search_domains = json.loads(task.get("search_domains_json") or "[]")
        recency_days = task.get("recency_days")
        knowledge_enabled = bool(task.get("knowledge_enabled"))
        knowledge_document_ids = json.loads(task.get("knowledge_document_ids_json") or "[]")
        existing_tokens = int(task.get("tokens_used") or 0)
        existing_prompt = int(task.get("prompt_tokens") or 0)
        existing_completion = int(task.get("completion_tokens") or 0)
        existing_cost = float(task.get("cost_rmb") or 0.0)
        existing_search_calls = int(task.get("search_calls") or 0)
        existing_crawl_calls = int(task.get("crawl_calls") or 0)
        existing_search_credits = int(task.get("search_credits") or 0)
        budget = budget_from_task(task)
        if len(plan.steps) > budget.max_steps:
            plan.steps = plan.steps[: budget.max_steps]
            update_task(
                task_id,
                plan_json=json.dumps(plan.model_dump(), ensure_ascii=False),
                total_steps=len(plan.steps),
            )
        researcher_model = task.get("researcher_model") or Config.RESEARCHER_MODEL
        reporter_model = task.get("reporter_model") or Config.REPORTER_MODEL
        researcher_output_limit = {
            "fast": 2048,
            "standard": 3072,
            "deep": 4096,
        }.get(budget.profile, 2048)
        _ensure_token_budget(existing_tokens, budget.max_tokens)

        # ---- Phase 1: Researching ----
        update_task(task_id, status="researching")
        await emitter.emit(
            "research.started",
            total_steps=len(plan.steps),
            steps=[s.title for s in plan.steps],
        )

        persisted_steps = {row["step_index"]: row for row in list_steps(task_id)}
        findings: list[ResearchFinding] = []
        total_sources = 0
        for step_num, row in persisted_steps.items():
            if row.get("status") != "completed":
                continue
            references = [
                SourceReference.model_validate(item)
                for item in json.loads(row.get("sources_json") or "[]")
            ]
            findings.append(
                ResearchFinding(
                    step_id=f"step_{step_num}",
                    step_title=row["title"],
                    problem_statement=row.get("description") or "",
                    findings_markdown=row.get("findings_markdown") or "",
                    conclusion=row.get("conclusion") or "",
                    references=references,
                )
            )
            total_sources += len(references)

        for i, step in enumerate(plan.steps):
            step_num = i + 1
            if persisted_steps.get(step_num, {}).get("status") == "completed":
                continue
            update_task(task_id, current_step=step_num)

            use_researcher = step.need_search or sandbox_tool_disabled()
            step_kind = "search" if use_researcher else "code"
            await emitter.emit(
                "step.started",
                step_index=step_num,
                title=step.title,
                step_type=step_kind,
                total_steps=len(plan.steps),
            )

            if use_researcher:
                local_refs = _build_local_references(
                    step.title + "\n" + step.description,
                    user_id=task.get("user_id"),
                    document_ids=knowledge_document_ids if knowledge_enabled else [],
                )
                phase_started = time.time()
                finding, pt, ct = await research_step(
                    step=step, step_index=step_num,
                    total_steps=len(plan.steps), locale=locale,
                    local_references=local_refs,
                    search_domains=search_domains,
                    recency_days=recency_days,
                    max_search_calls=budget.max_search_calls_per_step,
                    max_crawl_pages=budget.max_crawl_pages_per_step,
                    search_depth=budget.search_depth,
                    token_budget_remaining=(
                        budget.max_tokens
                        - existing_tokens
                        - total_prompt
                        - total_completion
                    ),
                    model_override=researcher_model,
                    max_summary_tokens=researcher_output_limit,
                )
            else:
                phase_started = time.time()
                finding, pt, ct = await process_step(
                    step=step, step_index=step_num,
                    total_steps=len(plan.steps), locale=locale,
                    previous_findings=findings,
                )
            tool_calls = (
                _build_research_tool_calls(finding, len(local_refs))
                if use_researcher
                else [{"tool": "python_sandbox", "count": 1}]
            )
            save_agent_run(
                task_id=task_id,
                agent_name="Researcher" if use_researcher else "Coder",
                phase=f"step_{step_num}",
                status="completed",
                input_summary=f"{step.title}\n{step.description}",
                output_summary=finding.conclusion or finding.findings_markdown[:1000],
                tool_calls=tool_calls,
                prompt_tokens=pt,
                completion_tokens=ct,
                elapsed_seconds=time.time() - phase_started,
            )
            total_prompt += pt
            total_completion += ct
            _ensure_token_budget(
                existing_tokens + total_prompt + total_completion,
                budget.max_tokens,
            )
            findings.append(finding)
            total_sources += len(finding.references)
            total_search_calls += finding.search_calls
            total_crawl_calls += finding.crawl_calls
            total_search_credits += finding.search_credits

            # 更新步骤
            step_id = f"{task_id}_step_{step_num}"
            update_step(
                step_id,
                status="completed",
                findings_markdown=finding.findings_markdown,
                conclusion=finding.conclusion,
                sources_json=[r.model_dump() for r in finding.references],
            )
            current_prompt = existing_prompt + total_prompt
            current_completion = existing_completion + total_completion
            current_tokens = existing_tokens + total_prompt + total_completion
            update_task(
                task_id,
                prompt_tokens=current_prompt,
                completion_tokens=current_completion,
                tokens_used=current_tokens,
                cost_rmb=existing_cost
                + estimate_cost_rmb(
                    researcher_model,
                    total_prompt,
                    total_completion,
                ),
                search_calls=existing_search_calls + total_search_calls,
                crawl_calls=existing_crawl_calls + total_crawl_calls,
                search_credits=existing_search_credits + total_search_credits,
                elapsed_seconds=time.time() - started_at,
            )

            await emitter.emit(
                "step.completed",
                step_index=step_num,
                title=step.title,
                sources_count=len(finding.references),
                total_sources_so_far=total_sources,
            )

        if not findings:
            raise RuntimeError("所有研究步骤均未产生有效发现")

        # ---- Phase 3: Reporting ----
        _ensure_token_budget(
            existing_tokens + total_prompt + total_completion,
            budget.max_tokens,
        )
        if budget.profile == "fast":
            report_output_limit = 1536
            finding_context_limit = 800
        elif budget.profile == "standard":
            report_output_limit = 4096
            finding_context_limit = 1600
        else:
            report_output_limit = 8192
            finding_context_limit = None
        _ensure_call_capacity(
            existing_tokens + total_prompt + total_completion,
            report_output_limit,
            budget.max_tokens,
        )
        update_task(task_id, status="generating_report", failed_phase="")
        await emitter.emit("report.started")

        phase_started = time.time()
        report, pt, ct = await generate_report(
            plan=plan,
            findings=findings,
            locale=locale,
            model_override=reporter_model,
            max_output_tokens=report_output_limit,
            max_finding_chars_per_step=finding_context_limit,
        )
        save_agent_run(
            task_id=task_id,
            agent_name="Reporter",
            phase="reporting",
            status="completed",
            input_summary=f"{plan.title}; findings={len(findings)}",
            output_summary=report[:2000],
            prompt_tokens=pt,
            completion_tokens=ct,
            elapsed_seconds=time.time() - phase_started,
        )
        total_prompt += pt
        total_completion += ct
        _ensure_token_budget(
            existing_tokens + total_prompt + total_completion,
            budget.max_tokens,
        )

        # ---- Done ----
        total_tokens = existing_tokens + total_prompt + total_completion
        research_prompt = total_prompt - pt
        research_completion = total_completion - ct
        total_cost = (
            existing_cost
            + estimate_cost_rmb(
                researcher_model,
                research_prompt,
                research_completion,
            )
            + estimate_cost_rmb(reporter_model, pt, ct)
        )
        now = datetime.now().isoformat()

        update_task(
            task_id,
            status="completed",
            report_markdown=report,
            sources_count=total_sources,
            search_calls=existing_search_calls + total_search_calls,
            crawl_calls=existing_crawl_calls + total_crawl_calls,
            search_credits=existing_search_credits + total_search_credits,
            prompt_tokens=existing_prompt + total_prompt,
            completion_tokens=existing_completion + total_completion,
            tokens_used=total_tokens,
            cost_rmb=total_cost,
            elapsed_seconds=time.time() - started_at,
            updated_at=now,
        )

        await emitter.emit(
            "report.completed",
            report_id=f"rep_{task_id}",
            title=plan.title,
            sources_count=total_sources,
            tokens_used=total_tokens,
        )

    except Exception as e:
        failure = classify_failure(e)
        logger.exception(
            "研究任务失败",
            extra={
                "task_id": task_id,
                "user_id": (task or {}).get("user_id"),
                "phase": (task or {}).get("status") or "researching",
                "elapsed": round(time.time() - started_at, 3),
                "error_code": failure.code,
            },
        )
        raise

    finally:
        remove_event_manager(task_id)


def _ensure_token_budget(total_tokens: int, max_tokens: int) -> None:
    """超过配置预算时中断任务。"""
    if max_tokens <= 0:
        return
    if total_tokens > max_tokens:
        raise RuntimeError(f"Token budget exceeded: {total_tokens} > {max_tokens}")


def _ensure_call_capacity(
    current_tokens: int,
    requested_output_tokens: int,
    max_tokens: int,
) -> None:
    if max_tokens > 0 and current_tokens + requested_output_tokens > max_tokens:
        raise RuntimeError(
            "Token budget exceeded before provider call: "
            f"current={current_tokens}, requested={requested_output_tokens}, "
            f"limit={max_tokens}"
        )


def _build_research_tool_calls(finding: ResearchFinding, knowledge_hits: int) -> list[dict]:
    """Build trace tool-call counters without changing the persisted schema."""
    calls = [
        {"tool": "web_search", "count": finding.search_calls},
        {"tool": "web_crawl", "count": finding.crawl_calls},
    ]
    if knowledge_hits > 0:
        calls.append({"tool": "knowledge_search", "count": knowledge_hits})
    return calls


def _build_local_references(
    query: str,
    user_id: str | None = None,
    document_ids: list[str] | None = None,
) -> list[SourceReference]:
    """把知识库向量检索结果转为 Researcher 可引用来源。"""
    if not document_ids:
        return []
    try:
        chunks = search_knowledge_chunks(
            query,
            limit=Config.KNOWLEDGE_TOP_K,
            user_id=user_id,
            document_ids=document_ids,
        )
    except EmbeddingError as exc:
        logger.warning("Knowledge retrieval skipped: %s", exc)
        return []

    refs: list[SourceReference] = []
    for chunk in chunks:
        page_num = chunk.get("page_num")
        page_label = f"page {page_num}" if page_num else "page unknown"
        retrieval_mode = chunk.get("retrieval_mode") or "hybrid"
        score = max(0.0, min(1.0, float(chunk.get("score") or 0.0)))
        source_name = chunk.get("source_name") or chunk.get("title") or chunk["doc_id"]
        snippet_header = (
            "[knowledge_base "
            f"doc_id={chunk['doc_id']} "
            f"chunk_id={chunk['chunk_id']} "
            f"chunk_index={chunk['chunk_index']} "
            f"page_num={page_num or ''} "
            f"score={score:.4f} "
            f"retrieval_mode={retrieval_mode}]"
        )
        refs.append(
            SourceReference(
                title=f"Knowledge Base: {source_name} | {page_label} | chunk {chunk['chunk_index']}",
                url=f"kb://{chunk['doc_id']}#{chunk['chunk_id']}",
                source_type=SourceType.KNOWLEDGE_BASE,
                snippet=f"{snippet_header}\n{(chunk.get('content') or '')[:2000]}",
                confidence=score,
            )
        )
    return refs
