"""Workspace, project, comments, and read-only sharing routes."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import require_login
from backend.app.core.access import require_artifact_access, require_task_access
from backend.app.repositories.auth import get_user_by_username
from backend.app.repositories import workspace as workspace_repository

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
    expires_in_days: int = Field(default=7, ge=1, le=365)


@router.get("")
async def list_workspaces(user: dict = Depends(require_login)):
    return workspace_repository.list_workspaces(user["user_id"])


@router.post("", status_code=201)
async def create_workspace(req: WorkspaceRequest, user: dict = Depends(require_login)):
    workspace_id = f"ws_{uuid.uuid4().hex[:12]}"
    return workspace_repository.create_workspace(
        workspace_id,
        user["user_id"],
        req.name,
        req.description,
    )


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, user: dict = Depends(require_login)):
    _require_workspace_role(workspace_id, user["user_id"])
    row = workspace_repository.get_workspace(workspace_id)
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    data = dict(row)
    data["members"] = workspace_repository.list_members(workspace_id)
    return data


@router.post("/{workspace_id}/members")
async def upsert_member(workspace_id: str, req: MemberRequest, user: dict = Depends(require_login)):
    _require_workspace_role(workspace_id, user["user_id"], allowed={"owner"})
    target = get_user_by_username(req.username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    workspace = workspace_repository.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if target["user_id"] == workspace["owner_user_id"] and req.role != "owner":
        raise HTTPException(status_code=409, detail="Workspace owner role cannot be changed")
    if target["user_id"] != workspace["owner_user_id"] and req.role == "owner":
        raise HTTPException(status_code=409, detail="Workspace ownership transfer is not supported")
    workspace_repository.upsert_member(workspace_id, target["user_id"], req.role)
    return {"workspace_id": workspace_id, "user_id": target["user_id"], "username": target["username"], "role": req.role}


@router.get("/{workspace_id}/projects")
async def list_projects(workspace_id: str, user: dict = Depends(require_login)):
    _require_workspace_role(workspace_id, user["user_id"])
    return workspace_repository.list_projects(workspace_id)


@router.post("/{workspace_id}/projects", status_code=201)
async def create_project(workspace_id: str, req: ProjectRequest, user: dict = Depends(require_login)):
    _require_workspace_role(workspace_id, user["user_id"], allowed=EDIT_ROLES)
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    return workspace_repository.create_project(
        project_id,
        workspace_id,
        user["user_id"],
        req.name,
        req.description,
    )


@router.post("/comments", status_code=201)
async def add_report_comment(req: CommentRequest, user: dict = Depends(require_login)):
    task = require_task_access(req.task_id, user["user_id"], write=True)
    comment_id = f"comment_{uuid.uuid4().hex[:12]}"
    return workspace_repository.create_comment(
        comment_id,
        task["task_id"],
        user["user_id"],
        req.anchor,
        req.content,
    )


@router.get("/comments/{task_id}")
async def list_report_comments(task_id: str, user: dict = Depends(require_login)):
    require_task_access(task_id, user["user_id"])
    return workspace_repository.list_comments(task_id)


@share_router.post("", status_code=201)
async def create_share_link(req: ShareLinkRequest, user: dict = Depends(require_login)):
    if req.resource_type == "task_report":
        resource = require_task_access(req.resource_id, user["user_id"], write=True)
    else:
        resource = require_artifact_access(req.resource_id, user["user_id"], write=True)
    token = secrets.token_urlsafe(24)
    share_id = f"share_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    expires_at = (datetime.now() + timedelta(days=req.expires_in_days)).isoformat()
    workspace_repository.create_share_link(
        {
            "share_id": share_id,
            "token": token,
            "user_id": user["user_id"],
            "resource_type": req.resource_type,
            "resource_id": req.resource_id,
            "workspace_id": resource.get("workspace_id"),
            "created_at": now,
            "expires_at": expires_at,
        }
    )
    return {
        "share_id": share_id,
        "token": token,
        "url": f"/shared/{token}",
        "resource_type": req.resource_type,
        "expires_at": expires_at,
    }


@share_router.delete("/{share_id}", status_code=204)
async def revoke_share_link(share_id: str, user: dict = Depends(require_login)):
    if not workspace_repository.revoke_share_link(share_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Shared link not found")
    return None


@public_router.get("/{token}")
async def get_shared_resource(token: str):
    share_dict, resource = workspace_repository.get_shared_resource(token)
    if not share_dict:
        raise HTTPException(status_code=404, detail="Shared link not found")
    if share_dict.get("revoked_at"):
        raise HTTPException(status_code=404, detail="Shared link not found")
    if share_dict.get("expires_at") and share_dict["expires_at"] <= datetime.now().isoformat():
        raise HTTPException(status_code=410, detail="Shared link has expired")
    if not resource:
        detail = "Report not found" if share_dict["resource_type"] == "task_report" else "Artifact not found"
        raise HTTPException(status_code=404, detail=detail)
    return {"share": share_dict, "resource": resource, "readonly": True}


def _require_workspace_role(workspace_id: str, user_id: str, allowed: set[str] | None = None) -> str:
    role = workspace_repository.get_member_role(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if allowed and role not in allowed:
        raise HTTPException(status_code=403, detail="Insufficient workspace permission")
    return role
