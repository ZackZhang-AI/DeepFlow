"""Persistent research events with SSE replay support."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from backend.app.core.db import get_connection


def append_event(task_id: str, event_type: str, data: dict) -> int:
    conn = get_connection()
    task = conn.execute(
        "SELECT user_id FROM research_tasks WHERE task_id = ?", (task_id,)
    ).fetchone()
    if task is None:
        conn.close()
        raise ValueError("Task not found")
    cursor = conn.execute(
        """INSERT INTO research_events (task_id, user_id, event_type, data_json, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (task_id, task["user_id"], event_type, json.dumps(data, ensure_ascii=False),
         datetime.now().isoformat()),
    )
    conn.commit()
    sequence = int(cursor.lastrowid)
    conn.close()
    return sequence


def list_events(task_id: str, after_seq: int = 0, limit: int = 200) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT sequence, event_type, data_json, created_at
           FROM research_events WHERE task_id = ? AND sequence > ?
           ORDER BY sequence LIMIT ?""",
        (task_id, after_seq, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "sequence": row["sequence"],
            "type": row["event_type"],
            "data": json.loads(row["data_json"] or "{}"),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_last_event_sequence(task_id: str) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM research_events WHERE task_id = ?",
        (task_id,),
    ).fetchone()
    conn.close()
    return int(row["sequence"] if row else 0)


class EventManager:
    def __init__(self, task_id: str):
        self.task_id = task_id

    async def emit(self, event_type: str, **data) -> None:
        append_event(self.task_id, event_type, data)

    async def stream(self, after_seq: int = 0) -> AsyncGenerator[str, None]:
        cursor = max(0, after_seq)
        yield (
            "event: connected\n"
            f"data: {json.dumps({'sequence': cursor, 'type': 'connected', 'data': {}})}\n\n"
        )
        idle_ticks = 0
        while True:
            events = list_events(self.task_id, cursor)
            if events:
                idle_ticks = 0
                for event in events:
                    cursor = event["sequence"]
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"id: {cursor}\nevent: {event['type']}\ndata: {payload}\n\n"
                    if event["type"] in ("report.completed", "error.fatal"):
                        return
            else:
                idle_ticks += 1
                if idle_ticks >= 30:
                    idle_ticks = 0
                    yield f": heartbeat {datetime.now().isoformat()}\n\n"
            await asyncio.sleep(0.5)


def get_event_manager(task_id: str) -> EventManager:
    return EventManager(task_id)


def remove_event_manager(task_id: str) -> None:
    # Kept for API compatibility. Events remain persisted for replay.
    return None
