"""Report version and generated artifact persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from backend.app.core.db import LOCAL_DEFAULT_USER_ID, get_connection
from backend.app.repositories.research import get_task

def save_report_version(
    task_id: str,
    content_markdown: str,
    change_note: str = "",
    user_id: str | None = None,
) -> str:
    version_id = f"ver_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    now = datetime.now().isoformat()
    task = get_task(task_id) or {}
    user_id = user_id or task.get("user_id") or LOCAL_DEFAULT_USER_ID
    conn = get_connection()
    conn.execute(
        """INSERT INTO report_versions
           (version_id, task_id, user_id, content_markdown, change_note,
            workspace_id, project_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            version_id,
            task_id,
            user_id,
            content_markdown,
            change_note,
            task.get("workspace_id"),
            task.get("project_id"),
            now,
        ),
    )
    conn.commit()
    conn.close()
    return version_id


def list_report_versions(task_id: str, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            """SELECT version_id, task_id, user_id, change_note, created_at, length(content_markdown) AS content_length
           FROM report_versions WHERE task_id = ? ORDER BY created_at DESC""",
            (task_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT version_id, task_id, user_id, change_note, created_at, length(content_markdown) AS content_length
           FROM report_versions WHERE task_id = ? AND user_id = ? ORDER BY created_at DESC""",
            (task_id, user_id),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report_version(version_id: str, user_id: str | None = None) -> Optional[dict]:
    conn = get_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM report_versions WHERE version_id = ?", (version_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM report_versions WHERE version_id = ? AND user_id = ?",
            (version_id, user_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_artifact(
    artifact_id: str,
    task_id: str,
    artifact_type: str,
    title: str,
    content: str,
    metadata: dict | None = None,
    user_id: str | None = None,
) -> dict:
    now = datetime.now().isoformat()
    task = get_task(task_id) or {}
    user_id = user_id or task.get("user_id") or LOCAL_DEFAULT_USER_ID
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO artifacts
           (artifact_id, task_id, user_id, artifact_type, title, content, metadata_json,
            workspace_id, project_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            artifact_id,
            task_id,
            user_id,
            artifact_type,
            title,
            content,
            json.dumps(metadata or {}, ensure_ascii=False),
            task.get("workspace_id"),
            task.get("project_id"),
            now,
        ),
    )
    conn.commit()
    conn.close()
    return get_artifact(artifact_id)


def get_artifact(artifact_id: str, user_id: str | None = None) -> Optional[dict]:
    conn = get_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ? AND user_id = ?",
            (artifact_id, user_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_artifacts(task_id: str, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            """SELECT artifact_id, task_id, user_id, artifact_type, title, metadata_json, created_at
           FROM artifacts WHERE task_id = ? ORDER BY created_at DESC""",
            (task_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT artifact_id, task_id, user_id, artifact_type, title, metadata_json, created_at
           FROM artifacts WHERE task_id = ? AND user_id = ? ORDER BY created_at DESC""",
            (task_id, user_id),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Agent Trace
# ============================================================
