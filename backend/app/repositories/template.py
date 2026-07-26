"""Research template persistence."""

from __future__ import annotations

import json
from datetime import datetime

from backend.app.core.db import get_connection


def list_templates(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT template_id, user_id, name, category, description, report_style,
                      created_at, updated_at
               FROM research_templates
               WHERE user_id = ?
               ORDER BY updated_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_template(template_id: str, user_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM research_templates WHERE template_id = ? AND user_id = ?",
            (template_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def create_template(template_id: str, user_id: str, data: dict) -> dict:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO research_templates
               (template_id, user_id, name, category, description,
                clarification_questions_json, plan_structure_json,
                recommended_domains_json, report_style, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                template_id,
                user_id,
                data["name"],
                data.get("category", ""),
                data.get("description", ""),
                json.dumps(data.get("clarification_questions", []), ensure_ascii=False),
                json.dumps(data.get("plan_structure", []), ensure_ascii=False),
                json.dumps(data.get("recommended_domains", []), ensure_ascii=False),
                data.get("report_style", "general"),
                now,
                now,
            ),
        )
        conn.commit()
    return get_template(template_id, user_id) or {}


def update_template(template_id: str, user_id: str, data: dict) -> dict | None:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE research_templates
               SET name = ?, category = ?, description = ?, clarification_questions_json = ?,
                   plan_structure_json = ?, recommended_domains_json = ?, report_style = ?,
                   updated_at = ?
               WHERE template_id = ? AND user_id = ?""",
            (
                data["name"],
                data.get("category", ""),
                data.get("description", ""),
                json.dumps(data.get("clarification_questions", []), ensure_ascii=False),
                json.dumps(data.get("plan_structure", []), ensure_ascii=False),
                json.dumps(data.get("recommended_domains", []), ensure_ascii=False),
                data.get("report_style", "general"),
                now,
                template_id,
                user_id,
            ),
        )
        conn.commit()
    return get_template(template_id, user_id) if cursor.rowcount else None


def delete_template(template_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM research_templates WHERE template_id = ? AND user_id = ?",
            (template_id, user_id),
        )
        conn.commit()
    return cursor.rowcount > 0
