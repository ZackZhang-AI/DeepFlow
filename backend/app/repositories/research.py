"""Research task, step, and trace persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from backend.app.core.db import LOCAL_DEFAULT_USER_ID, get_connection

def _task_user_id(task_id: str) -> str:
    task = get_task(task_id)
    return (task or {}).get("user_id") or LOCAL_DEFAULT_USER_ID


def create_task(
    task_id: str,
    topic: str,
    locale: str = "zh-CN",
    search_domains: list[str] | None = None,
    recency_days: int | None = None,
    knowledge_enabled: bool = False,
    knowledge_document_ids: list[str] | None = None,
    user_id: str = LOCAL_DEFAULT_USER_ID,
    workspace_id: str | None = None,
    project_id: str | None = None,
    budget_profile: str = "fast",
    max_steps: int = 3,
    max_search_calls_per_step: int = 1,
    max_crawl_pages_per_step: int = 1,
    max_tokens_budget: int = 30_000,
    search_depth: str = "basic",
    planner_model: str = "deepseek-v4-flash",
    researcher_model: str = "deepseek-v4-flash",
    reporter_model: str = "deepseek-v4-flash",
    pricing_version: str = "",
) -> dict:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO research_tasks
           (task_id, user_id, topic, locale, status, search_domains_json, recency_days,
            knowledge_enabled, knowledge_document_ids_json,
            workspace_id, project_id, budget_profile, max_steps,
            max_search_calls_per_step, max_crawl_pages_per_step, max_tokens_budget,
            search_depth, planner_model, researcher_model, reporter_model, pricing_version,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, 'coordinating', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            task_id,
            user_id,
            topic,
            locale,
            json.dumps(search_domains or [], ensure_ascii=False),
            recency_days,
            1 if knowledge_enabled else 0,
            json.dumps(knowledge_document_ids or [], ensure_ascii=False),
            workspace_id,
            project_id,
            budget_profile,
            max_steps,
            max_search_calls_per_step,
            max_crawl_pages_per_step,
            max_tokens_budget,
            search_depth,
            planner_model,
            researcher_model,
            reporter_model,
            pricing_version,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return get_task(task_id)


def get_task(task_id: str, user_id: str | None = None) -> Optional[dict]:
    conn = get_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM research_tasks WHERE task_id = ?", (task_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM research_tasks WHERE task_id = ? AND user_id = ?",
            (task_id, user_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_task(task_id: str, owner_user_id: str | None = None, **kwargs) -> Optional[dict]:
    kwargs["updated_at"] = datetime.now().isoformat()
    if "errors_json" in kwargs and isinstance(kwargs["errors_json"], list):
        kwargs["errors_json"] = json.dumps(kwargs["errors_json"], ensure_ascii=False)

    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())

    conn = get_connection()
    if owner_user_id is None:
        conn.execute(f"UPDATE research_tasks SET {set_clause} WHERE task_id = ?", values + [task_id])
    else:
        conn.execute(
            f"UPDATE research_tasks SET {set_clause} WHERE task_id = ? AND user_id = ?",
            values + [task_id, owner_user_id],
        )
    conn.commit()
    conn.close()
    return get_task(task_id, owner_user_id)


def list_tasks(limit: int = 20, offset: int = 0, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            "SELECT * FROM research_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM research_tasks t
               WHERE t.user_id = ?
                  OR EXISTS (
                      SELECT 1 FROM workspace_members m
                      WHERE m.workspace_id = t.workspace_id AND m.user_id = ?
                  )
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (user_id, user_id, limit, offset),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_usage_summary(user_id: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        """SELECT
               COUNT(1) AS total_tasks,
               SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_tasks,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_tasks,
               COALESCE(SUM(cost_rmb), 0) AS total_cost_rmb,
               COALESCE(AVG(CASE WHEN status = 'completed' THEN cost_rmb END), 0) AS avg_cost_rmb,
               COALESCE(SUM(tokens_used), 0) AS total_tokens,
               COALESCE(SUM(search_credits), 0) AS total_search_credits
           FROM research_tasks
           WHERE user_id = ?""",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row)


def save_step(
    task_id: str,
    step_index: int,
    title: str,
    description: str,
    need_search: bool = True,
    user_id: str | None = None,
) -> str:
    step_id = f"{task_id}_step_{step_index}"
    user_id = user_id or _task_user_id(task_id)
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO research_steps
           (step_id, task_id, user_id, step_index, title, description, need_search, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (step_id, task_id, user_id, step_index, title, description, 1 if need_search else 0),
    )
    conn.commit()
    conn.close()
    return step_id


def update_step(step_id: str, **kwargs) -> None:
    if "sources_json" in kwargs and isinstance(kwargs["sources_json"], list):
        kwargs["sources_json"] = json.dumps(kwargs["sources_json"], ensure_ascii=False)

    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())

    conn = get_connection()
    conn.execute(f"UPDATE research_steps SET {set_clause} WHERE step_id = ?", values + [step_id])
    conn.commit()
    conn.close()


def list_steps(task_id: str, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            "SELECT * FROM research_steps WHERE task_id = ? ORDER BY step_index",
            (task_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM research_steps
               WHERE task_id = ? AND user_id = ? ORDER BY step_index""",
            (task_id, user_id),
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_agent_run(
    task_id: str,
    agent_name: str,
    phase: str,
    status: str,
    input_summary: str = "",
    output_summary: str = "",
    tool_calls: list[dict] | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    elapsed_seconds: float = 0.0,
    error: str = "",
    user_id: str | None = None,
) -> dict:
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    now = datetime.now().isoformat()
    user_id = user_id or _task_user_id(task_id)
    conn = get_connection()
    conn.execute(
        """INSERT INTO agent_runs
           (run_id, task_id, user_id, agent_name, phase, status, input_summary, output_summary,
            tool_calls_json, prompt_tokens, completion_tokens, elapsed_seconds, error, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            task_id,
            user_id,
            agent_name,
            phase,
            status,
            input_summary[:2000],
            output_summary[:4000],
            json.dumps(tool_calls or [], ensure_ascii=False),
            prompt_tokens,
            completion_tokens,
            elapsed_seconds,
            error[:2000],
            now,
        ),
    )
    conn.commit()
    conn.close()
    return get_agent_run(run_id)


def get_agent_run(run_id: str, user_id: str | None = None) -> Optional[dict]:
    conn = get_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM agent_runs WHERE run_id = ? AND user_id = ?",
            (run_id, user_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_agent_runs(task_id: str, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            "SELECT * FROM agent_runs WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agent_runs WHERE task_id = ? AND user_id = ? ORDER BY created_at ASC",
            (task_id, user_id),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
