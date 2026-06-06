"""
SSE 事件流 API
"""

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.core.db import get_task
from backend.app.core.events import get_event_manager

router = APIRouter(prefix="/api/research-tasks", tags=["events"])


@router.get("/{task_id}/events")
async def stream_events(task_id: str):
    """
    SSE 事件流 — 前端 EventSource 消费。

    事件类型:
    - coordinator.started
    - planner.completed
    - step.started / step.completed
    - report.started / report.completed
    - error.fatal
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    emitter = get_event_manager(task_id)

    async def event_generator():
        async for chunk in emitter.stream():
            yield chunk
            await asyncio.sleep(0.01)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
