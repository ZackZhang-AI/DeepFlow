"""Workspace, collaboration, and sharing persistence."""

from __future__ import annotations

import json
from datetime import datetime

from backend.app.core.db import get_connection


def list_workspaces(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT w.*, m.role
               FROM workspaces w
               JOIN workspace_members m ON m.workspace_id = w.workspace_id
               WHERE m.user_id = ?
               ORDER BY w.updated_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_workspace(
    workspace_id: str,
    owner_user_id: str,
    name: str,
    description: str,
) -> dict:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO workspaces
               (workspace_id, owner_user_id, name, description, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (workspace_id, owner_user_id, name, description, now, now),
        )
        conn.execute(
            """INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
               VALUES (?, ?, 'owner', ?)""",
            (workspace_id, owner_user_id, now),
        )
        conn.commit()
    return get_workspace(workspace_id) or {}


def get_workspace(workspace_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
    return dict(row) if row else None


def list_members(workspace_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT m.user_id, u.username, m.role, m.created_at
               FROM workspace_members m
               LEFT JOIN users u ON u.user_id = m.user_id
               WHERE m.workspace_id = ?
               ORDER BY m.created_at ASC""",
            (workspace_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_member_role(workspace_id: str, user_id: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id),
        ).fetchone()
    return str(row["role"]) if row else None


def upsert_member(workspace_id: str, user_id: str, role: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(workspace_id, user_id) DO UPDATE SET role = excluded.role""",
            (workspace_id, user_id, role, datetime.now().isoformat()),
        )
        conn.commit()


def list_projects(workspace_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE workspace_id = ? ORDER BY updated_at DESC",
            (workspace_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_project(project_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return dict(row) if row else None


def create_project(
    project_id: str,
    workspace_id: str,
    owner_user_id: str,
    name: str,
    description: str,
) -> dict:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO projects
               (project_id, workspace_id, owner_user_id, name, description, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (project_id, workspace_id, owner_user_id, name, description, now, now),
        )
        conn.commit()
    return get_project(project_id) or {}


def create_comment(
    comment_id: str,
    task_id: str,
    user_id: str,
    anchor: str,
    content: str,
) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO report_comments
               (comment_id, task_id, user_id, anchor, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (comment_id, task_id, user_id, anchor, content, datetime.now().isoformat()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM report_comments WHERE comment_id = ?",
            (comment_id,),
        ).fetchone()
    return dict(row)


def list_comments(task_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.*, u.username
               FROM report_comments c
               LEFT JOIN users u ON u.user_id = c.user_id
               WHERE c.task_id = ?
               ORDER BY c.created_at ASC""",
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_share_link(data: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO shared_links
               (share_id, token, user_id, resource_type, resource_id,
                workspace_id, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["share_id"],
                data["token"],
                data["user_id"],
                data["resource_type"],
                data["resource_id"],
                data.get("workspace_id"),
                data["created_at"],
                data.get("expires_at"),
            ),
        )
        conn.commit()


def revoke_share_link(share_id: str, user_id: str) -> bool:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        share = conn.execute(
            "SELECT * FROM shared_links WHERE share_id = ? AND revoked_at IS NULL",
            (share_id,),
        ).fetchone()
        if not share:
            return False
        share = dict(share)
        allowed = share["user_id"] == user_id
        if not allowed and share.get("workspace_id"):
            role = conn.execute(
                """SELECT role FROM workspace_members
                   WHERE workspace_id = ? AND user_id = ?""",
                (share["workspace_id"], user_id),
            ).fetchone()
            allowed = bool(role and role["role"] == "owner")
        if not allowed:
            return False
        cursor = conn.execute(
            "UPDATE shared_links SET revoked_at = ? WHERE share_id = ? AND revoked_at IS NULL",
            (now, share_id),
        )
        conn.commit()
    return cursor.rowcount > 0


def get_shared_resource(token: str) -> tuple[dict | None, dict | None]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM shared_links WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            return None, None
        share = dict(row)
        if share["resource_type"] == "task_report":
            resource = conn.execute(
                """SELECT task_id, topic, report_markdown, sources_count, tokens_used,
                          elapsed_seconds, updated_at, is_demo
                   FROM research_tasks
                   WHERE task_id = ? AND report_markdown IS NOT NULL
                         AND report_markdown != ''""",
                (share["resource_id"],),
            ).fetchone()
            resource = dict(resource) if resource else None
            if resource:
                resource["is_demo"] = bool(resource["is_demo"])
                resource["sources"] = _normalized_public_sources(conn, resource["task_id"])
        else:
            resource = conn.execute(
                """SELECT artifact_id, task_id, artifact_type, title, content,
                          created_at,
                          COALESCE((SELECT is_demo FROM research_tasks t
                                    WHERE t.task_id = artifacts.task_id), 0) AS is_demo
                   FROM artifacts WHERE artifact_id = ?""",
                (share["resource_id"],),
            ).fetchone()
            resource = dict(resource) if resource else None
            if resource:
                resource["is_demo"] = bool(resource["is_demo"])
                resource["sources"] = []
    return share, resource


def _normalized_public_sources(conn, task_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT sources_json FROM research_steps WHERE task_id = ? ORDER BY step_index",
        (task_id,),
    ).fetchall()
    normalized: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        try:
            sources = json.loads(row["sources_json"] or "[]")
        except (TypeError, json.JSONDecodeError):
            continue
        for source in sources if isinstance(sources, list) else []:
            if isinstance(source, str):
                url = source.strip()
                title = url
                source_type = "web"
            elif isinstance(source, dict):
                url = str(source.get("url") or source.get("link") or "").strip()
                title = str(
                    source.get("title")
                    or source.get("name")
                    or source.get("source_name")
                    or url
                ).strip()
                source_type = str(source.get("source_type") or source.get("type") or "web").strip()
            else:
                continue
            if not url.lower().startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            normalized.append({"title": title or url, "url": url, "source_type": source_type or "web"})
    return normalized
