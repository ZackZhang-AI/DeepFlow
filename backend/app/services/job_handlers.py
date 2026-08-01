"""Job handler registration kept separate from the queue infrastructure."""

import asyncio

from backend.app.core.job_queue import register_job_handler
from backend.app.services.research import execute_research_task, generate_research_plan_task
from backend.app.services.knowledge import process_pending_document


async def _plan(job: dict) -> None:
    payload = job["payload"]
    await generate_research_plan_task(
        task_id=job["task_id"],
        topic=payload["topic"],
        locale=payload.get("locale", "zh-CN"),
        max_steps=payload.get("max_steps"),
    )


async def _research(job: dict) -> None:
    await execute_research_task(job["task_id"])


async def _knowledge(job: dict) -> None:
    await asyncio.to_thread(
        process_pending_document,
        job["payload"]["doc_id"],
        job["user_id"],
    )


def register_handlers() -> None:
    register_job_handler("research_plan", _plan)
    register_job_handler("research_execute", _research)
    register_job_handler("knowledge_index", _knowledge)
