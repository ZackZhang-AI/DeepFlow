"""Research template routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import require_login
from backend.app.repositories.research import create_task, update_task
from backend.app.core.readiness import require_research_providers
from backend.app.repositories import template as template_repository
from cli.budget import get_budget
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
    return template_repository.list_templates(user["user_id"])


@router.post("", status_code=201)
async def create_template(req: TemplateRequest, user: dict = Depends(require_login)):
    template_id = f"tmpl_{uuid.uuid4().hex[:12]}"
    row = template_repository.create_template(template_id, user["user_id"], req.model_dump())
    return _public_template(row)


@router.get("/{template_id}")
async def get_template(template_id: str, user: dict = Depends(require_login)):
    template = template_repository.get_template(template_id, user["user_id"])
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _public_template(template)


@router.put("/{template_id}")
async def update_template(template_id: str, req: TemplateRequest, user: dict = Depends(require_login)):
    if not template_repository.get_template(template_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Template not found")
    row = template_repository.update_template(template_id, user["user_id"], req.model_dump())
    return _public_template(row or {})


@router.delete("/{template_id}")
async def delete_template(template_id: str, user: dict = Depends(require_login)):
    if not template_repository.delete_template(template_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"deleted": True, "template_id": template_id}


@router.post("/{template_id}/start-research", status_code=201)
async def start_research_from_template(
    template_id: str,
    req: StartFromTemplateRequest,
    user: dict = Depends(require_login),
):
    require_research_providers()
    template = template_repository.get_template(template_id, user["user_id"])
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    domains = json.loads(template.get("recommended_domains_json") or "[]")
    task = create_task(task_id, req.topic, req.locale, search_domains=domains, user_id=user["user_id"])
    plan_structure = json.loads(template.get("plan_structure_json") or "[]")
    plan_structure = plan_structure[: get_budget("fast").max_steps]
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
    task = update_task(
        task_id,
        owner_user_id=user["user_id"],
        clarification_json=json.dumps(questions, ensure_ascii=False),
        plan_json=json.dumps(plan, ensure_ascii=False) if plan else None,
        status="awaiting_confirmation" if plan_structure else "clarifying",
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
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
