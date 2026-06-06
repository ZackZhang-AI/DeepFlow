"""
研究任务服务 — 后台异步执行研究流程

复用 CLI 的 Agent 和状态机，封装为 FastAPI 后台任务。
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 path 中
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from cli.config import Config
from cli.models import ResearchPlan, ResearchFinding, RunRecord
from cli.agents.planner import generate_plan
from cli.agents.researcher import research_step
from cli.agents.coder import process_step
from cli.agents.reporter import generate_report
from backend.app.core.db import (
    update_task, save_step, update_step, get_task,
)
from backend.app.core.events import get_event_manager, remove_event_manager

logger = logging.getLogger("deepflow.backend")


async def execute_research_task(task_id: str, topic: str, locale: str = "zh-CN"):
    """
    后台执行完整研究任务。
    每个阶段都通过 EventManager 推送进度事件。
    """
    emitter = get_event_manager(task_id)
    total_prompt = 0
    total_completion = 0
    total_cost = 0.0
    errors = []

    try:
        # ---- Phase 1: Planning ----
        await emitter.emit("coordinator.started", task_id=task_id)
        update_task(task_id, status="planning")

        plan, pt, ct = await generate_plan(
            topic=topic, locale=locale, max_steps=Config.MAX_STEPS
        )
        total_prompt += pt
        total_completion += ct

        # 保存计划到数据库
        plan_dict = plan.model_dump()
        update_task(
            task_id,
            status="awaiting_confirmation",
            plan_json=json.dumps(plan_dict, ensure_ascii=False),
            total_steps=len(plan.steps),
            updated_at=datetime.now().isoformat(),
        )

        await emitter.emit(
            "planner.completed",
            plan=plan_dict,
            steps_count=len(plan.steps),
        )

        # 保存步骤
        for i, step in enumerate(plan.steps):
            save_step(task_id, i + 1, step.title, step.description, step.need_search)

        # ---- Phase 2: Researching ----
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
                finding, pt, ct = await research_step(
                    step=step, step_index=step_num,
                    total_steps=len(plan.steps), locale=locale,
                )
            else:
                finding, pt, ct = await process_step(
                    step=step, step_index=step_num,
                    total_steps=len(plan.steps), locale=locale,
                )
            total_prompt += pt
            total_completion += ct
            findings.append(finding)
            total_sources += len(finding.references)

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
        update_task(task_id, status="generating_report")
        await emitter.emit("report.started")

        report, pt, ct = await generate_report(
            plan=plan, findings=findings, locale=locale
        )
        total_prompt += pt
        total_completion += ct

        # ---- Done ----
        total_tokens = total_prompt + total_completion
        total_cost = _estimate_cost(total_prompt, total_completion)
        now = datetime.now().isoformat()

        update_task(
            task_id,
            status="completed",
            report_markdown=report,
            sources_count=total_sources,
            tokens_used=total_tokens,
            cost_rmb=total_cost,
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
