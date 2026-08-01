"""Workflow and workflow-run persistence."""

from __future__ import annotations

import json
from datetime import datetime

from backend.app.core.db import get_connection


def list_workflows(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM workflows
               WHERE user_id = ?
               ORDER BY updated_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_workflow(workflow_id: str, user_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workflows WHERE workflow_id = ? AND user_id = ?",
            (workflow_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def create_workflow(workflow_id: str, user_id: str, data: dict) -> dict:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO workflows
               (workflow_id, user_id, name, description, nodes_json, edges_json,
                budget_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                workflow_id,
                user_id,
                data["name"],
                data.get("description", ""),
                json.dumps(data.get("nodes", []), ensure_ascii=False),
                json.dumps(data.get("edges", []), ensure_ascii=False),
                json.dumps(data.get("budget", {}), ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
    return get_workflow(workflow_id, user_id) or {}


def update_workflow(workflow_id: str, user_id: str, data: dict) -> dict | None:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE workflows
               SET name = ?, description = ?, nodes_json = ?, edges_json = ?,
                   budget_json = ?, updated_at = ?
               WHERE workflow_id = ? AND user_id = ?""",
            (
                data["name"],
                data.get("description", ""),
                json.dumps(data.get("nodes", []), ensure_ascii=False),
                json.dumps(data.get("edges", []), ensure_ascii=False),
                json.dumps(data.get("budget", {}), ensure_ascii=False),
                now,
                workflow_id,
                user_id,
            ),
        )
        conn.commit()
    return get_workflow(workflow_id, user_id) if cursor.rowcount else None


def delete_workflow(workflow_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM workflows WHERE workflow_id = ? AND user_id = ?",
            (workflow_id, user_id),
        )
        conn.commit()
    return cursor.rowcount > 0


def create_run(
    run_id: str,
    workflow_id: str,
    user_id: str,
    workflow_input: dict,
) -> dict:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO workflow_runs
               (run_id, workflow_id, user_id, status, input_json, outputs_json,
                error, created_at, updated_at)
               VALUES (?, ?, ?, 'running', ?, '{}', '', ?, ?)""",
            (
                run_id,
                workflow_id,
                user_id,
                json.dumps(workflow_input, ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
    return get_run(run_id, user_id) or {}


def get_run(run_id: str, user_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workflow_runs WHERE run_id = ? AND user_id = ?",
            (run_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def update_run(run_id: str, user_id: str, result: dict) -> dict | None:
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE workflow_runs
               SET status = ?, outputs_json = ?, error = ?, updated_at = ?
               WHERE run_id = ? AND user_id = ?""",
            (
                result["status"],
                json.dumps(result, ensure_ascii=False),
                str(result.get("error") or "")[:2000],
                datetime.now().isoformat(),
                run_id,
                user_id,
            ),
        )
        conn.commit()
    return get_run(run_id, user_id) if cursor.rowcount else None


def list_runs(workflow_id: str, user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM workflow_runs
               WHERE workflow_id = ? AND user_id = ?
               ORDER BY created_at DESC""",
            (workflow_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


def list_node_runs(run_id: str, user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM workflow_node_runs
               WHERE run_id = ? AND user_id = ?
               ORDER BY created_at ASC""",
            (run_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


def save_node_run(data: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO workflow_node_runs
               (node_run_id, run_id, workflow_id, user_id, node_id, node_type, status,
                input_summary, output_summary, tool_calls_json, elapsed_seconds, error,
                created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["node_run_id"],
                data["run_id"],
                data["workflow_id"],
                data["user_id"],
                data["node_id"],
                data["node_type"],
                data["status"],
                data.get("input_summary", ""),
                data.get("output_summary", ""),
                json.dumps(data.get("tool_calls", []), ensure_ascii=False),
                data.get("elapsed_seconds", 0.0),
                data.get("error", ""),
                data.get("created_at") or datetime.now().isoformat(),
            ),
        )
        conn.commit()
