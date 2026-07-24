"""Research template routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import require_login
from backend.app.core.db import create_task, get_connection
from backend.app.core.readiness import require_research_providers
from cli.models import ResearchPlan, ResearchStep, StepType

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: str = ""
    description: str = ""
    clarification_questions: list[str] = Field(default_factory=list)
    plan_structure: list[dict] = Field(default_factory=list)
    recommended_domains: list[str] = Field(default_factory=list)
    report_style: str = "general"


class StartFromTemplateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    locale: str = "zh-CN"


@router.get("")
async def list_templates(user: dict = Depends(require_login)):
    conn = get_connection()
    rows = conn.execute(
        """SELECT template_id, user_id, name, category, description, report_style, created_at, updated_at
           FROM research_templates
           WHERE user_id = ?
           ORDER BY updated_at DESC""",
        (user["user_id"],),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@router.post("", status_code=201)
async def create_template(req: TemplateRequest, user: dict = Depends(require_login)):
    template_id = f"tmpl_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO research_templates
           (template_id, user_id, name, category, description, clarification_questions_json,
            plan_structure_json, recommended_domains_json, report_style, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            template_id,
            user["user_id"],
            req.name,
            req.category,
            req.description,
            json.dumps(req.clarification_questions, ensure_ascii=False),
            json.dumps(req.plan_structure, ensure_ascii=False),
            json.dumps(req.recommended_domains, ensure_ascii=False),
            req.report_style,
            now,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM research_templates WHERE template_id = ?", (template_id,)).fetchone()
    conn.close()
    return _public_template(dict(row))


@router.get("/{template_id}")
async def get_template(template_id: str, user: dict = Depends(require_login)):
    template = _get_template(template_id, user["user_id"])
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _public_template(template)


@router.put("/{template_id}")
async def update_template(template_id: str, req: TemplateRequest, user: dict = Depends(require_login)):
    if not _get_template(template_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Template not found")
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """UPDATE research_templates
           SET name = ?, category = ?, description = ?, clarification_questions_json = ?,
               plan_structure_json = ?, recommended_domains_json = ?, report_style = ?, updated_at = ?
           WHERE template_id = ? AND user_id = ?""",
        (
            req.name,
            req.category,
            req.description,
            json.dumps(req.clarification_questions, ensure_ascii=False),
            json.dumps(req.plan_structure, ensure_ascii=False),
            json.dumps(req.recommended_domains, ensure_ascii=False),
            req.report_style,
            now,
            template_id,
            user["user_id"],
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM research_templates WHERE template_id = ?", (template_id,)).fetchone()
    conn.close()
    return _public_template(dict(row))


@router.delete("/{template_id}")
async def delete_template(template_id: str, user: dict = Depends(require_login)):
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM research_templates WHERE template_id = ? AND user_id = ?",
        (template_id, user["user_id"]),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"deleted": True, "template_id": template_id}


@router.post("/{template_id}/start-research", status_code=201)
async def start_research_from_template(
    template_id: str,
    req: StartFromTemplateRequest,
    user: dict = Depends(require_login),
):
    require_research_providers()
    template = _get_template(template_id, user["user_id"])
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    domains = json.loads(template.get("recommended_domains_json") or "[]")
    task = create_task(task_id, req.topic, req.locale, search_domains=domains, user_id=user["user_id"])
    plan_structure = json.loads(template.get("plan_structure_json") or "[]")
    questions = json.loads(template.get("clarification_questions_json") or "[]")
    plan = (
        _build_template_plan(
            topic=req.topic,
            locale=req.locale,
            template_id=template_id,
            report_style=template["report_style"],
            plan_structure=plan_structure,
        )
        if plan_structure
        else None
    )
    conn = get_connection()
    conn.execute(
        """UPDATE research_tasks
           SET clarification_json = ?, plan_json = ?, status = ?, updated_at = ?
           WHERE task_id = ? AND user_id = ?""",
        (
            json.dumps(questions, ensure_ascii=False),
            json.dumps(plan, ensure_ascii=False) if plan else None,
            "awaiting_confirmation" if plan_structure else "clarifying",
            datetime.now().isoformat(),
            task_id,
            user["user_id"],
        ),
    )
    conn.commit()
    conn.close()
    task["template_id"] = template_id
    task["status"] = "awaiting_confirmation" if plan_structure else "clarifying"
    return task


def _build_template_plan(
    *,
    topic: str,
    locale: str,
    template_id: str,
    report_style: str,
    plan_structure: list[dict],
) -> dict:
    """Normalize legacy template steps into the canonical research plan schema."""
    steps: list[ResearchStep] = []
    for index, raw_step in enumerate(plan_structure, start=1):
        title = str(
            raw_step.get("title")
            or raw_step.get("name")
            or raw_step.get("label")
            or f"研究步骤 {index}"
        ).strip()
        description = str(
            raw_step.get("description")
            or raw_step.get("objective")
            or raw_step.get("query")
            or raw_step.get("prompt")
            or title
        ).strip()
        raw_type = str(raw_step.get("step_type") or raw_step.get("type") or "").lower()
        need_search = bool(
            raw_step.get(
                "need_search",
                raw_step.get("search_required", raw_type != StepType.PROCESSING.value),
            )
        )
        step_type = (
            StepType.PROCESSING
            if raw_type in {StepType.PROCESSING.value, "process", "analysis", "analyze"}
            else StepType.RESEARCH
        )
        if step_type == StepType.PROCESSING:
            need_search = False
        steps.append(
            ResearchStep(
                title=title,
                description=description,
                need_search=need_search,
                step_type=step_type,
            )
        )

    validated = ResearchPlan(
        title=topic,
        locale=locale,
        has_enough_context=True,
        thought=f"Research plan created from template {template_id}.",
        steps=steps,
    )
    payload = validated.model_dump(mode="json")
    payload["template_id"] = template_id
    payload["style"] = report_style
    return payload


def _get_template(template_id: str, user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM research_templates WHERE template_id = ? AND user_id = ?",
        (template_id, user_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _public_template(row: dict) -> dict:
    return {
        "template_id": row["template_id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "category": row["category"],
        "description": row["description"],
        "clarification_questions": json.loads(row.get("clarification_questions_json") or "[]"),
        "plan_structure": json.loads(row.get("plan_structure_json") or "[]"),
        "recommended_domains": json.loads(row.get("recommended_domains_json") or "[]"),
        "report_style": row["report_style"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
