"""Workspace, project, comments, and read-only sharing routes."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import require_login
from backend.app.core.db import get_connection, get_task, get_user_by_username

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
share_router = APIRouter(prefix="/api/share-links", tags=["share-links"])
public_router = APIRouter(prefix="/api/shared", tags=["shared"])

ROLES = {"owner", "editor", "viewer"}
EDIT_ROLES = {"owner", "editor"}


class WorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = ""


class MemberRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    role: str = Field(..., pattern="^(owner|editor|viewer)$")


class ProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = ""


class CommentRequest(BaseModel):
    task_id: str
    anchor: str = ""
    content: str = Field(..., min_length=1, max_length=4000)


class ShareLinkRequest(BaseModel):
    resource_type: str = Field(..., pattern="^(task_report|artifact)$")
    resource_id: str = Field(..., min_length=1, max_length=200)


@router.get("")
async def list_workspaces(user: dict = Depends(require_login)):
    conn = get_connection()
    rows = conn.execute(
        """SELECT w.*, m.role
           FROM workspaces w
           JOIN workspace_members m ON m.workspace_id = w.workspace_id
           WHERE m.user_id = ?
           ORDER BY w.updated_at DESC""",
        (user["user_id"],),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@router.post("", status_code=201)
async def create_workspace(req: WorkspaceRequest, user: dict = Depends(require_login)):
    now = datetime.now().isoformat()
    workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    conn.execute(
        """INSERT INTO workspaces (workspace_id, owner_user_id, name, description, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (workspace_id, user["user_id"], req.name, req.description, now, now),
    )
    conn.execute(
        """INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
           VALUES (?, ?, 'owner', ?)""",
        (workspace_id, user["user_id"], now),
    )
    conn.commit()
    row = conn.execute(
        """SELECT w.*, 'owner' AS role FROM workspaces w WHERE w.workspace_id = ?""",
        (workspace_id,),
    ).fetchone()
    conn.close()
    return dict(row)


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, user: dict = Depends(require_login)):
    _require_workspace_role(workspace_id, user["user_id"])
    conn = get_connection()
    row = conn.execute("SELECT * FROM workspaces WHERE workspace_id = ?", (workspace_id,)).fetchone()
    members = conn.execute(
        """SELECT m.user_id, u.username, m.role, m.created_at
           FROM workspace_members m
           LEFT JOIN users u ON u.user_id = m.user_id
           WHERE m.workspace_id = ?
           ORDER BY m.created_at ASC""",
        (workspace_id,),
    ).fetchall()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    data = dict(row)
    data["members"] = [dict(member) for member in members]
    return data


@router.post("/{workspace_id}/members")
async def upsert_member(workspace_id: str, req: MemberRequest, user: dict = Depends(require_login)):
    _require_workspace_role(workspace_id, user["user_id"], allowed={"owner"})
    target = get_user_by_username(req.username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO workspace_members (workspace_id, user_id, role, created_at)
           VALUES (?, ?, ?, ?)""",
        (workspace_id, target["user_id"], req.role, now),
    )
    conn.commit()
    conn.close()
    return {"workspace_id": workspace_id, "user_id": target["user_id"], "username": target["username"], "role": req.role}


@router.get("/{workspace_id}/projects")
async def list_projects(workspace_id: str, user: dict = Depends(require_login)):
    _require_workspace_role(workspace_id, user["user_id"])
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM projects WHERE workspace_id = ? ORDER BY updated_at DESC""",
        (workspace_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@router.post("/{workspace_id}/projects", status_code=201)
async def create_project(workspace_id: str, req: ProjectRequest, user: dict = Depends(require_login)):
    _require_workspace_role(workspace_id, user["user_id"], allowed=EDIT_ROLES)
    now = datetime.now().isoformat()
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    conn.execute(
        """INSERT INTO projects (project_id, workspace_id, owner_user_id, name, description, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (project_id, workspace_id, user["user_id"], req.name, req.description, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    conn.close()
    return dict(row)


@router.post("/comments", status_code=201)
async def add_report_comment(req: CommentRequest, user: dict = Depends(require_login)):
    task = _require_task_access(req.task_id, user["user_id"], allowed=EDIT_ROLES)
    comment_id = f"comment_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO report_comments (comment_id, task_id, user_id, anchor, content, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (comment_id, task["task_id"], user["user_id"], req.anchor, req.content, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM report_comments WHERE comment_id = ?", (comment_id,)).fetchone()
    conn.close()
    return dict(row)


@router.get("/comments/{task_id}")
async def list_report_comments(task_id: str, user: dict = Depends(require_login)):
    _require_task_access(task_id, user["user_id"])
    conn = get_connection()
    rows = conn.execute(
        """SELECT c.*, u.username
           FROM report_comments c
           LEFT JOIN users u ON u.user_id = c.user_id
           WHERE c.task_id = ?
           ORDER BY c.created_at ASC""",
        (task_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@share_router.post("", status_code=201)
async def create_share_link(req: ShareLinkRequest, user: dict = Depends(require_login)):
    if req.resource_type == "task_report":
        _require_task_access(req.resource_id, user["user_id"])
    else:
        _require_owned_artifact(req.resource_id, user["user_id"])
    token = secrets.token_urlsafe(24)
    share_id = f"share_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO shared_links (share_id, token, user_id, resource_type, resource_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (share_id, token, user["user_id"], req.resource_type, req.resource_id, now),
    )
    conn.commit()
    conn.close()
    return {"share_id": share_id, "token": token, "url": f"/shared/{token}", "resource_type": req.resource_type}


@public_router.get("/{token}")
async def get_shared_resource(token: str):
    conn = get_connection()
    share = conn.execute("SELECT * FROM shared_links WHERE token = ?", (token,)).fetchone()
    if not share:
        conn.close()
        raise HTTPException(status_code=404, detail="Shared link not found")
    share_dict = dict(share)
    if share_dict["resource_type"] == "task_report":
        row = conn.execute(
            """SELECT task_id, topic, report_markdown, sources_count, tokens_used, elapsed_seconds, updated_at
               FROM research_tasks WHERE task_id = ? AND report_markdown IS NOT NULL AND report_markdown != ''""",
            (share_dict["resource_id"],),
        ).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        return {"share": share_dict, "resource": dict(row), "readonly": True}
    row = conn.execute(
        """SELECT artifact_id, task_id, artifact_type, title, content, metadata_json, created_at
           FROM artifacts WHERE artifact_id = ?""",
        (share_dict["resource_id"],),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"share": share_dict, "resource": dict(row), "readonly": True}


def _require_workspace_role(workspace_id: str, user_id: str, allowed: set[str] | None = None) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
        (workspace_id, user_id),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    role = row["role"]
    if allowed and role not in allowed:
        raise HTTPException(status_code=403, detail="Insufficient workspace permission")
    return role


def _require_task_access(task_id: str, user_id: str, allowed: set[str] | None = None) -> dict[str, Any]:
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("user_id") == user_id:
        return task
    workspace_id = task.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=404, detail="Task not found")
    role = _require_workspace_role(workspace_id, user_id, allowed)
    if allowed and role not in allowed:
        raise HTTPException(status_code=403, detail="Insufficient task permission")
    return task


def _require_owned_artifact(artifact_id: str, user_id: str) -> None:
    conn = get_connection()
    row = conn.execute(
        "SELECT artifact_id FROM artifacts WHERE artifact_id = ? AND user_id = ?",
        (artifact_id, user_id),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Artifact not found")
