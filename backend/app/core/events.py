"""
SSE 事件管理器 — 支持研究进度实时推送
"""

import asyncio
import json
from typing import AsyncGenerator


class EventManager:
    """
    每个研究任务对应一个 EventManager 实例。
    后端服务向 EventManager 推送事件，前端通过 SSE 消费。
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._queue: asyncio.Queue = asyncio.Queue()

    async def emit(self, event_type: str, **data) -> None:
        """推送事件"""
        event = {"type": event_type, "data": data}
        await self._queue.put(event)

    async def stream(self) -> AsyncGenerator[str, None]:
        """SSE 流 — 前端 EventSource 消费"""
        yield "data: {\"type\":\"connected\",\"data\":{}}\n\n"

        while True:
            event = await self._queue.get()
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

            if event["type"] in ("report.completed", "error.fatal"):
                break


# 全局事件管理器注册表
_event_managers: dict[str, EventManager] = {}


def get_event_manager(task_id: str) -> EventManager:
    """获取或创建事件管理器"""
    if task_id not in _event_managers:
        _event_managers[task_id] = EventManager(task_id)
    return _event_managers[task_id]


def remove_event_manager(task_id: str) -> None:
    """任务完成后清理"""
    _event_managers.pop(task_id, None)
