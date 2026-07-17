"""Server-Sent Events for research task progress."""

import asyncio

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.app.core.auth import get_user_from_token
from backend.app.core.db import get_task
from backend.app.core.events import get_event_manager

router = APIRouter(prefix="/api/research-tasks", tags=["events"])


@router.get("/{task_id}/events")
async def stream_events(task_id: str, token: str = Query(default="")):
    """Stream task progress through EventSource.

    EventSource cannot set Authorization headers, so the frontend passes the
    bearer token as a query parameter for this endpoint only.
    """
    user = get_user_from_token(token) if token else None
    if user is None:
      raise HTTPException(status_code=401, detail="Authentication required")

    task = get_task(task_id, user_id=user["user_id"])
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

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
