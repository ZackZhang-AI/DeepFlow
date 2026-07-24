"""Configurable Agent workflow routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import require_login
from backend.app.core.db import get_connection
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
    conn = get_connection()
    rows = conn.execute(
        """SELECT workflow_id, user_id, name, description, nodes_json, edges_json, budget_json, created_at, updated_at
           FROM workflows
           WHERE user_id = ?
           ORDER BY updated_at DESC""",
        (user["user_id"],),
    ).fetchall()
    conn.close()
    return [_public_workflow(dict(row)) for row in rows]


@router.post("", status_code=201)
async def create_workflow(req: WorkflowRequest, user: dict = Depends(require_login)):
    _validate_nodes(req.nodes)
    workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO workflows
           (workflow_id, user_id, name, description, nodes_json, edges_json, budget_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            workflow_id,
            user["user_id"],
            req.name,
            req.description,
            json.dumps(req.nodes, ensure_ascii=False),
            json.dumps(req.edges, ensure_ascii=False),
            json.dumps(req.budget, ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)).fetchone()
    conn.close()
    return _public_workflow(dict(row))


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, user: dict = Depends(require_login)):
    workflow = _get_workflow(workflow_id, user["user_id"])
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _public_workflow(workflow)


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, req: WorkflowRequest, user: dict = Depends(require_login)):
    if not _get_workflow(workflow_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Workflow not found")
    _validate_nodes(req.nodes)
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """UPDATE workflows
           SET name = ?, description = ?, nodes_json = ?, edges_json = ?, budget_json = ?, updated_at = ?
           WHERE workflow_id = ? AND user_id = ?""",
        (
            req.name,
            req.description,
            json.dumps(req.nodes, ensure_ascii=False),
            json.dumps(req.edges, ensure_ascii=False),
            json.dumps(req.budget, ensure_ascii=False),
            now,
            workflow_id,
            user["user_id"],
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)).fetchone()
    conn.close()
    return _public_workflow(dict(row))


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, user: dict = Depends(require_login)):
    conn = get_connection()
    cur = conn.execute("DELETE FROM workflows WHERE workflow_id = ? AND user_id = ?", (workflow_id, user["user_id"]))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"deleted": True, "workflow_id": workflow_id}


@router.post("/{workflow_id}/runs", status_code=201)
async def run_workflow(workflow_id: str, req: RunWorkflowRequest, user: dict = Depends(require_login)):
    workflow = _get_workflow(workflow_id, user["user_id"])
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    run_id = f"wfr_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO workflow_runs
           (run_id, workflow_id, user_id, status, input_json, outputs_json, error, created_at, updated_at)
           VALUES (?, ?, ?, 'running', ?, '{}', '', ?, ?)""",
        (run_id, workflow_id, user["user_id"], json.dumps(req.input, ensure_ascii=False), now, now),
    )
    conn.commit()
    conn.close()

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

    conn = get_connection()
    conn.execute(
        """UPDATE workflow_runs SET status = ?, outputs_json = ?, error = ?, updated_at = ?
           WHERE run_id = ? AND user_id = ?""",
        (
            final["status"],
            json.dumps(final, ensure_ascii=False),
            str(final.get("error") or "")[:2000],
            datetime.now().isoformat(),
            run_id,
            user["user_id"],
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    return _public_run(dict(row))


@router.post("/runs/{run_id}/resume")
async def resume_workflow_run(
    run_id: str,
    req: ResumeWorkflowRequest,
    user: dict = Depends(require_login),
):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM workflow_runs WHERE run_id = ? AND user_id = ?",
        (run_id, user["user_id"]),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    run = dict(row)
    if run["status"] != "waiting_feedback":
        raise HTTPException(status_code=409, detail="Workflow run is not waiting for feedback")

    workflow = _get_workflow(run["workflow_id"], user["user_id"])
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

    conn = get_connection()
    conn.execute(
        """UPDATE workflow_runs SET status = ?, outputs_json = ?, error = ?, updated_at = ?
           WHERE run_id = ? AND user_id = ?""",
        (
            final["status"],
            json.dumps(final, ensure_ascii=False),
            str(final.get("error") or "")[:2000],
            datetime.now().isoformat(),
            run_id,
            user["user_id"],
        ),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    return _public_run(dict(updated))


@router.get("/{workflow_id}/runs")
async def list_workflow_runs(workflow_id: str, user: dict = Depends(require_login)):
    if not _get_workflow(workflow_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Workflow not found")
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM workflow_runs
           WHERE workflow_id = ? AND user_id = ?
           ORDER BY created_at DESC""",
        (workflow_id, user["user_id"]),
    ).fetchall()
    conn.close()
    return [_public_run(dict(row)) for row in rows]


@router.get("/runs/{run_id}/trace")
async def get_workflow_trace(run_id: str, user: dict = Depends(require_login)):
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM workflow_node_runs
           WHERE run_id = ? AND user_id = ?
           ORDER BY created_at ASC""",
        (run_id, user["user_id"]),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _get_workflow(workflow_id: str, user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM workflows WHERE workflow_id = ? AND user_id = ?",
        (workflow_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


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
