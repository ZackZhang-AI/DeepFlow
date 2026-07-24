"""Central resource access checks for personal and workspace-owned data."""

from __future__ import annotations

from fastapi import HTTPException

from backend.app.core.db import get_connection, get_task

WRITE_ROLES = {"owner", "editor"}


def require_scope_access(
    user_id: str,
    workspace_id: str | None,
    project_id: str | None,
    *,
    write: bool,
) -> None:
    if not workspace_id and not project_id:
        return
    conn = get_connection()
    if project_id:
        project = conn.execute(
            "SELECT workspace_id FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        if not project or (workspace_id and project["workspace_id"] != workspace_id):
            conn.close()
            raise HTTPException(status_code=404, detail="Project not found")
        workspace_id = project["workspace_id"]
    member = conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
        (workspace_id, user_id),
    ).fetchone()
    conn.close()
    if not member:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if write and member["role"] not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Viewer access is read-only")


def require_task_access(task_id: str, user_id: str, *, write: bool = False) -> dict:
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("user_id") == user_id:
        return task
    if not task.get("workspace_id"):
        raise HTTPException(status_code=404, detail="Task not found")
    require_scope_access(
        user_id,
        task.get("workspace_id"),
        task.get("project_id"),
        write=write,
    )
    return task
