"""Central resource access checks for personal and workspace-owned data."""

from __future__ import annotations

from fastapi import HTTPException

from backend.app.repositories.artifact import get_artifact, get_report_version
from backend.app.repositories.knowledge import get_knowledge_document
from backend.app.repositories.research import get_task
from backend.app.repositories.workspace import get_member_role, get_project

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
    if project_id:
        project = get_project(project_id)
        if not project or (workspace_id and project["workspace_id"] != workspace_id):
            raise HTTPException(status_code=404, detail="Project not found")
        workspace_id = project["workspace_id"]
    role = get_member_role(str(workspace_id), user_id)
    if not role:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if write and role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Viewer access is read-only")


def require_task_access(task_id: str, user_id: str, *, write: bool = False) -> dict:
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.get("workspace_id") and task.get("user_id") == user_id:
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


def require_knowledge_access(doc_id: str, user_id: str, *, write: bool = False) -> dict:
    document = get_knowledge_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document.get("workspace_id") and document.get("user_id") == user_id:
        return document
    if not document.get("workspace_id"):
        raise HTTPException(status_code=404, detail="Document not found")
    require_scope_access(
        user_id,
        document.get("workspace_id"),
        document.get("project_id"),
        write=write,
    )
    return document


def require_artifact_access(artifact_id: str, user_id: str, *, write: bool = False) -> dict:
    artifact = get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if not artifact.get("workspace_id") and artifact.get("user_id") == user_id:
        return artifact
    if not artifact.get("workspace_id"):
        raise HTTPException(status_code=404, detail="Artifact not found")
    require_scope_access(
        user_id,
        artifact.get("workspace_id"),
        artifact.get("project_id"),
        write=write,
    )
    return artifact


def require_report_version_access(version_id: str, user_id: str) -> dict:
    version = get_report_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    if not version.get("workspace_id") and version.get("user_id") == user_id:
        return version
    if not version.get("workspace_id"):
        raise HTTPException(status_code=404, detail="Version not found")
    require_scope_access(
        user_id,
        version.get("workspace_id"),
        version.get("project_id"),
        write=False,
    )
    return version
