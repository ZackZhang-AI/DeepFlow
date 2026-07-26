"""Configurable Agent workflow routes."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import require_login
from backend.app.repositories import workflow as workflow_repository
from backend.app.services.workflow_runner import (
    SUPPORTED_NODE_TYPES,
    apply_feedback,
    execute_workflow,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

class WorkflowRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)


class RunWorkflowRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


class ResumeWorkflowRequest(BaseModel):
    feedback: Any


@router.get("")
async def list_workflows(user: dict = Depends(require_login)):
    return [_public_workflow(row) for row in workflow_repository.list_workflows(user["user_id"])]


@router.post("", status_code=201)
async def create_workflow(req: WorkflowRequest, user: dict = Depends(require_login)):
    _validate_nodes(req.nodes)
    workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
    row = workflow_repository.create_workflow(workflow_id, user["user_id"], req.model_dump())
    return _public_workflow(row)


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, user: dict = Depends(require_login)):
    workflow = workflow_repository.get_workflow(workflow_id, user["user_id"])
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _public_workflow(workflow)


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, req: WorkflowRequest, user: dict = Depends(require_login)):
    if not workflow_repository.get_workflow(workflow_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Workflow not found")
    _validate_nodes(req.nodes)
    row = workflow_repository.update_workflow(
        workflow_id,
        user["user_id"],
        req.model_dump(),
    )
    return _public_workflow(row or {})


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, user: dict = Depends(require_login)):
    if not workflow_repository.delete_workflow(workflow_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"deleted": True, "workflow_id": workflow_id}


@router.post("/{workflow_id}/runs", status_code=201)
async def run_workflow(workflow_id: str, req: RunWorkflowRequest, user: dict = Depends(require_login)):
    workflow = workflow_repository.get_workflow(workflow_id, user["user_id"])
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    run_id = f"wfr_{uuid.uuid4().hex[:12]}"
    workflow_repository.create_run(run_id, workflow_id, user["user_id"], req.input)

    try:
        nodes = json.loads(workflow["nodes_json"] or "[]")
        budget = json.loads(workflow["budget_json"] or "{}")
        final = await execute_workflow(
            nodes=nodes,
            workflow_input=req.input,
            user=user,
            workflow_id=workflow_id,
            run_id=run_id,
            budget=budget,
        )
    except Exception as exc:
        final = {
            "status": "failed",
            "outputs": {},
            "trace": [],
            "next_node_index": 0,
            "token_usage": 0,
            "execution_mode": "sequential",
            "edges_applied": False,
            "error": str(exc),
        }

    row = workflow_repository.update_run(run_id, user["user_id"], final)
    return _public_run(row or {})


@router.post("/runs/{run_id}/resume")
async def resume_workflow_run(
    run_id: str,
    req: ResumeWorkflowRequest,
    user: dict = Depends(require_login),
):
    run = workflow_repository.get_run(run_id, user["user_id"])
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if run["status"] != "waiting_feedback":
        raise HTTPException(status_code=409, detail="Workflow run is not waiting for feedback")

    workflow = workflow_repository.get_workflow(run["workflow_id"], user["user_id"])
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    checkpoint = apply_feedback(json.loads(run.get("outputs_json") or "{}"), req.feedback)
    workflow_input = json.loads(run.get("input_json") or "{}")
    workflow_input["human_feedback"] = checkpoint["feedback"]
    final = await execute_workflow(
        nodes=json.loads(workflow["nodes_json"] or "[]"),
        workflow_input=workflow_input,
        user=user,
        workflow_id=workflow["workflow_id"],
        run_id=run_id,
        budget=json.loads(workflow["budget_json"] or "{}"),
        checkpoint=checkpoint,
        start_index=checkpoint["next_node_index"],
    )

    updated = workflow_repository.update_run(run_id, user["user_id"], final)
    return _public_run(updated or {})


@router.get("/{workflow_id}/runs")
async def list_workflow_runs(workflow_id: str, user: dict = Depends(require_login)):
    if not workflow_repository.get_workflow(workflow_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return [
        _public_run(row)
        for row in workflow_repository.list_runs(workflow_id, user["user_id"])
    ]


@router.get("/runs/{run_id}/trace")
async def get_workflow_trace(run_id: str, user: dict = Depends(require_login)):
    return workflow_repository.list_node_runs(run_id, user["user_id"])


def _validate_nodes(nodes: list[dict[str, Any]]) -> None:
    for node in nodes:
        node_type = str(node.get("type") or "")
        if node_type not in SUPPORTED_NODE_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported workflow node type: {node_type}")


def _public_workflow(row: dict) -> dict:
    return {
        "workflow_id": row["workflow_id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "description": row["description"],
        "nodes": json.loads(row.get("nodes_json") or "[]"),
        "edges": json.loads(row.get("edges_json") or "[]"),
        "budget": json.loads(row.get("budget_json") or "{}"),
        "execution_mode": "sequential",
        "edges_applied": False,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _public_run(row: dict) -> dict:
    return {
        "run_id": row["run_id"],
        "workflow_id": row["workflow_id"],
        "user_id": row["user_id"],
        "status": row["status"],
        "input": json.loads(row.get("input_json") or "{}"),
        "outputs": json.loads(row.get("outputs_json") or "{}"),
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
