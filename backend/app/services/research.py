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
from cli.models import ResearchPlan, ResearchFinding, SourceReference, SourceType
from cli.agents.planner import generate_plan
from cli.agents.researcher import research_step
from cli.agents.coder import process_step
from cli.agents.reporter import generate_report
from backend.app.core.db import update_task, save_step, update_step, get_task, save_agent_run
from backend.app.core.events import get_event_manager, remove_event_manager
from backend.app.services.embedding import EmbeddingError
from backend.app.services.knowledge import search_knowledge_chunks

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
    errors: list[str] = []

    try:
        await emitter.emit("coordinator.started", task_id=task_id)
        update_task(task_id, status="planning")

        phase_started = time.time()
        plan, pt, ct = await generate_plan(
            topic=topic,
            locale=locale,
            max_steps=max_steps or Config.MAX_STEPS,
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
        _ensure_token_budget(pt + ct)

        plan_dict = plan.model_dump()
        update_task(
            task_id,
            status="awaiting_confirmation",
            plan_json=json.dumps(plan_dict, ensure_ascii=False),
            total_steps=len(plan.steps),
            tokens_used=pt + ct,
            cost_rmb=_estimate_cost(pt, ct),
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
        logger.exception(f"研究计划生成失败: {task_id}")
        errors.append(str(e))
        update_task(task_id, status="failed", errors_json=errors)
        await emitter.emit("error.fatal", message=str(e))
        remove_event_manager(task_id)


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
    errors: list[str] = []
    started_at = time.time()

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
        existing_tokens = int(task.get("tokens_used") or 0)
        existing_cost = float(task.get("cost_rmb") or 0.0)
        _ensure_token_budget(existing_tokens)

        # ---- Phase 1: Researching ----
        update_task(task_id, status="researching")
        await emitter.emit(
            "research.started",
            total_steps=len(plan.steps),
            steps=[s.title for s in plan.steps],
        )

        findings: list[ResearchFinding] = []
        total_sources = 0

        for i, step in enumerate(plan.steps):
            step_num = i + 1
            update_task(task_id, current_step=step_num)

            step_kind = "search" if step.need_search else "code"
            await emitter.emit(
                "step.started",
                step_index=step_num,
                title=step.title,
                step_type=step_kind,
                total_steps=len(plan.steps),
            )

            if step.need_search:
                local_refs = _build_local_references(
                    step.title + "\n" + step.description,
                    user_id=task.get("user_id"),
                )
                phase_started = time.time()
                finding, pt, ct = await research_step(
                    step=step, step_index=step_num,
                    total_steps=len(plan.steps), locale=locale,
                    local_references=local_refs,
                    search_domains=search_domains,
                    recency_days=recency_days,
                )
            else:
                phase_started = time.time()
                finding, pt, ct = await process_step(
                    step=step, step_index=step_num,
                    total_steps=len(plan.steps), locale=locale,
                    previous_findings=findings,
                )
            tool_calls = (
                _build_research_tool_calls(finding, len(local_refs) if step.need_search else 0)
                if step.need_search
                else [{"tool": "python_sandbox", "count": 1}]
            )
            save_agent_run(
                task_id=task_id,
                agent_name="Researcher" if step.need_search else "Coder",
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
            _ensure_token_budget(existing_tokens + total_prompt + total_completion)
            findings.append(finding)
            total_sources += len(finding.references)
            total_search_calls += finding.search_calls
            total_crawl_calls += finding.crawl_calls

            # 更新步骤
            step_id = f"{task_id}_step_{step_num}"
            update_step(
                step_id,
                status="completed",
                findings_markdown=finding.findings_markdown,
                conclusion=finding.conclusion,
                sources_json=[r.model_dump() for r in finding.references],
            )

            await emitter.emit(
                "step.completed",
                step_index=step_num,
                title=step.title,
                sources_count=len(finding.references),
                total_sources_so_far=total_sources,
            )

        if not findings:
            errors.append("所有研究步骤均未产生有效发现")
            update_task(task_id, status="failed", errors_json=errors)
            await emitter.emit("error.fatal", message=errors[-1])
            return

        # ---- Phase 3: Reporting ----
        _ensure_token_budget(existing_tokens + total_prompt + total_completion)
        update_task(task_id, status="generating_report")
        await emitter.emit("report.started")

        phase_started = time.time()
        report, pt, ct = await generate_report(
            plan=plan, findings=findings, locale=locale
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
        _ensure_token_budget(existing_tokens + total_prompt + total_completion)

        # ---- Done ----
        total_tokens = existing_tokens + total_prompt + total_completion
        total_cost = existing_cost + _estimate_cost(total_prompt, total_completion)
        now = datetime.now().isoformat()

        update_task(
            task_id,
            status="completed",
            report_markdown=report,
            sources_count=total_sources,
            search_calls=total_search_calls,
            crawl_calls=total_crawl_calls,
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
        logger.exception(f"研究任务失败: {task_id}")
        errors.append(str(e))
        update_task(task_id, status="failed", errors_json=errors)
        await emitter.emit("error.fatal", message=str(e))

    finally:
        remove_event_manager(task_id)


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """估算费用（DeepSeek V4-Pro 定价）"""
    # V4-Pro: 输入 ¥3/百万, 输出 ¥6/百万
    prompt_cost = prompt_tokens / 1_000_000 * 3
    completion_cost = completion_tokens / 1_000_000 * 6
    return round(prompt_cost + completion_cost, 4)


def _ensure_token_budget(total_tokens: int) -> None:
    """超过配置预算时中断任务。"""
    if Config.MAX_TOKEN_BUDGET <= 0:
        return
    if total_tokens > Config.MAX_TOKEN_BUDGET:
        raise RuntimeError(f"Token 预算超限: {total_tokens} > {Config.MAX_TOKEN_BUDGET}")


def _build_research_tool_calls(finding: ResearchFinding, knowledge_hits: int) -> list[dict]:
    """Build trace tool-call counters without changing the persisted schema."""
    calls = [
        {"tool": "web_search", "count": finding.search_calls},
        {"tool": "web_crawl", "count": finding.crawl_calls},
    ]
    if knowledge_hits > 0:
        calls.append({"tool": "knowledge_search", "count": knowledge_hits})
    return calls


def _build_local_references(query: str, user_id: str | None = None) -> list[SourceReference]:
    """把知识库向量检索结果转为 Researcher 可引用来源。"""
    try:
        chunks = search_knowledge_chunks(query, limit=Config.KNOWLEDGE_TOP_K, user_id=user_id)
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
