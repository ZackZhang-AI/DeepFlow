"""SQLite-backed in-process job queue.

The database is the source of truth. The asyncio worker only claims and runs
jobs, so queued or interrupted work can be recovered after a process restart.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from backend.app.core.db import get_connection, update_task
from backend.app.core.errors import classify_failure
from backend.app.core.events import append_event

JobHandler = Callable[[dict], Awaitable[None]]
logger = logging.getLogger("deepflow.jobs")

_handlers: dict[str, JobHandler] = {}
_worker_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


def register_job_handler(job_type: str, handler: JobHandler) -> None:
    _handlers[job_type] = handler


def enqueue_job(
    job_type: str,
    *,
    user_id: str,
    task_id: str | None = None,
    payload: dict | None = None,
    max_attempts: int = 3,
) -> str:
    job_id = f"job_{uuid.uuid4().hex}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO background_jobs
           (job_id, task_id, user_id, job_type, status, payload_json, max_attempts,
            run_after, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?)""",
        (job_id, task_id, user_id, job_type, json.dumps(payload or {}, ensure_ascii=False),
         max_attempts, now, now, now),
    )
    conn.commit()
    conn.close()
    return job_id


def recover_interrupted_jobs(stale_seconds: int = 30) -> int:
    cutoff = (datetime.now() - timedelta(seconds=stale_seconds)).isoformat()
    now = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.execute(
        """UPDATE background_jobs
           SET status = 'queued', locked_at = NULL, heartbeat_at = NULL, updated_at = ?
           WHERE status = 'running' AND COALESCE(heartbeat_at, locked_at, '') < ?""",
        (now, cutoff),
    )
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return count


def _claim_next_job() -> dict | None:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        """SELECT * FROM background_jobs
           WHERE status IN ('queued', 'retry_wait') AND run_after <= ?
           ORDER BY created_at LIMIT 1""",
        (now,),
    ).fetchone()
    if row is None:
        conn.commit()
        conn.close()
        return None
    cursor = conn.execute(
        """UPDATE background_jobs
           SET status = 'running', attempt_count = attempt_count + 1,
               locked_at = ?, heartbeat_at = ?, updated_at = ?
           WHERE job_id = ? AND status IN ('queued', 'retry_wait')""",
        (now, now, now, row["job_id"]),
    )
    conn.commit()
    claimed = dict(row) if cursor.rowcount == 1 else None
    if claimed:
        claimed["attempt_count"] = int(claimed["attempt_count"]) + 1
        claimed["payload"] = json.loads(claimed.get("payload_json") or "{}")
    conn.close()
    return claimed


def _finish_job(job: dict) -> None:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """UPDATE background_jobs SET status = 'completed', updated_at = ?,
           heartbeat_at = ? WHERE job_id = ?""",
        (now, now, job["job_id"]),
    )
    conn.commit()
    conn.close()


async def _heartbeat(job: dict) -> None:
    while True:
        await asyncio.sleep(5)
        now = datetime.now().isoformat()
        conn = get_connection()
        conn.execute(
            """UPDATE background_jobs SET heartbeat_at = ?, updated_at = ?
               WHERE job_id = ? AND status = 'running'""",
            (now, now, job["job_id"]),
        )
        conn.commit()
        conn.close()
        if job.get("task_id"):
            update_task(job["task_id"], last_heartbeat_at=now)


def _fail_job(job: dict, exc: BaseException) -> None:
    failure = classify_failure(exc)
    attempts = int(job["attempt_count"])
    retryable = failure.retryable and attempts < int(job["max_attempts"])
    delay = min(30, 2 ** max(0, attempts - 1))
    now = datetime.now()
    conn = get_connection()
    conn.execute(
        """UPDATE background_jobs
           SET status = ?, run_after = ?, error_code = ?, error_message = ?, updated_at = ?
           WHERE job_id = ?""",
        (
            "retry_wait" if retryable else "failed",
            (now + timedelta(seconds=delay)).isoformat(),
            failure.code,
            failure.message[:2000],
            now.isoformat(),
            job["job_id"],
        ),
    )
    conn.commit()
    conn.close()
    if job.get("task_id"):
        task_id = job["task_id"]
        conn = get_connection()
        task = conn.execute(
            "SELECT status FROM research_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        conn.close()
        failed_phase = "reporting" if task and task["status"] == "generating_report" else (
            "planning" if job["job_type"] == "research_plan" else "researching"
        )
        update_task(
            task_id,
            status="queued" if retryable else "failed",
            attempt_count=attempts,
            error_code=failure.code,
            error_message=failure.message[:2000],
            retryable=1 if retryable or failure.retryable else 0,
            failed_phase=failed_phase,
        )
        append_event(
            task_id,
            "job.retrying" if retryable else "error.fatal",
            {
                "message": failure.message,
                "error_code": failure.code,
                "retryable": failure.retryable,
                "attempt": attempts,
            },
        )


async def _worker_loop() -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        job = _claim_next_job()
        if job is None:
            try:
                await asyncio.wait_for(_stop_event.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
            continue
        handler = _handlers.get(job["job_type"])
        if handler is None:
            _fail_job(job, RuntimeError(f"No handler registered for {job['job_type']}"))
            continue
        try:
            if job.get("task_id"):
                update_task(
                    job["task_id"],
                    attempt_count=job["attempt_count"],
                    last_heartbeat_at=datetime.now().isoformat(),
                    error_code="",
                    error_message="",
                )
            heartbeat_task = asyncio.create_task(_heartbeat(job))
            try:
                await handler(job)
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            _finish_job(job)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Background job failed", extra={"job_id": job["job_id"]})
            _fail_job(job, exc)


async def start_job_worker() -> None:
    global _worker_task, _stop_event
    if _worker_task and not _worker_task.done():
        return
    recover_interrupted_jobs()
    _stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(_worker_loop(), name="deepflow-job-worker")


async def stop_job_worker() -> None:
    global _worker_task, _stop_event
    if _stop_event:
        _stop_event.set()
    if _worker_task:
        try:
            await asyncio.wait_for(_worker_task, timeout=3)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _worker_task.cancel()
        _worker_task = None
