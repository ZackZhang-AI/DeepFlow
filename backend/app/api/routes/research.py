"""
研究任务 API 路由
"""

import uuid
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from backend.app.models.schemas import (
    AgentRunResponse,
    ClarificationAnswerRequest,
    CreateResearchRequest,
    ResearchTaskResponse,
    ConfirmPlanRequest,
)
from backend.app.core.db import create_task, get_task, update_task, list_tasks, list_agent_runs
from backend.app.core.auth import require_login
from backend.app.core.events import get_event_manager, remove_event_manager
from backend.app.services.research import execute_research_task, generate_research_plan_task

router = APIRouter(prefix="/api/research-tasks", tags=["research"])


@router.post("", response_model=ResearchTaskResponse, status_code=201)
async def create_research_task(
    req: CreateResearchRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_login),
):
    """创建研究任务并启动后台计划生成，等待用户确认后执行。"""
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    # 创建数据库记录
    task = create_task(
        task_id,
        req.topic,
        req.locale,
        search_domains=req.search_domains,
        recency_days=req.recency_days,
        user_id=user["user_id"],
    )

    clarification_questions = _build_clarification_questions(req.topic)
    if clarification_questions:
        task = update_task(
            task_id,
            owner_user_id=user["user_id"],
            status="clarifying",
            clarification_json=json.dumps(clarification_questions, ensure_ascii=False),
        )
        return ResearchTaskResponse(
            task_id=task["task_id"],
            topic=task["topic"],
            locale=task["locale"],
            status=task["status"],
            clarification_questions=clarification_questions,
            created_at=task["created_at"],
            updated_at=task["updated_at"],
        )

    # 先生成研究计划，等待用户确认后再跑研究链路
    background_tasks.add_task(
        generate_research_plan_task,
        task_id=task_id,
        topic=req.topic,
        locale=req.locale,
        max_steps=req.max_steps,
    )

    return ResearchTaskResponse(
        task_id=task["task_id"],
        topic=task["topic"],
        locale=task["locale"],
        status=task["status"],
        clarification_questions=[],
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


@router.get("/{task_id}", response_model=ResearchTaskResponse)
async def get_research_task(task_id: str, user: dict = Depends(require_login)):
    """查询研究任务状态"""
    task = get_task(task_id, user_id=user["user_id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ResearchTaskResponse(
        task_id=task["task_id"],
        topic=task["topic"],
        locale=task["locale"],
        status=task["status"],
        current_step=task["current_step"] or 0,
        total_steps=task["total_steps"] or 0,
        report_id=f"rep_{task_id}" if task["report_markdown"] else None,
        clarification_questions=json.loads(task.get("clarification_json") or "[]"),
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


@router.get("")
async def list_research_tasks(limit: int = 20, offset: int = 0, user: dict = Depends(require_login)):
    """获取任务列表"""
    tasks = list_tasks(limit=limit, offset=offset, user_id=user["user_id"])
    return [
        ResearchTaskResponse(
            task_id=t["task_id"],
            topic=t["topic"],
            locale=t["locale"],
            status=t["status"],
            current_step=t["current_step"] or 0,
            total_steps=t["total_steps"] or 0,
            clarification_questions=json.loads(t.get("clarification_json") or "[]"),
            created_at=t["created_at"],
            updated_at=t["updated_at"],
        )
        for t in tasks
    ]


@router.post("/{task_id}/clarifications", response_model=ResearchTaskResponse)
async def answer_clarifications(
    task_id: str,
    req: ClarificationAnswerRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_login),
):
    """提交澄清回答，并启动计划生成。"""
    task = get_task(task_id, user_id=user["user_id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] != "clarifying":
        raise HTTPException(status_code=400, detail=f"当前状态不需要澄清: {task['status']}")

    answers = [v.strip() for v in req.answers.values() if v.strip()]
    enriched_topic = task["topic"]
    if answers:
        enriched_topic += "\n\n用户补充信息：\n" + "\n".join(f"- {answer}" for answer in answers)

    task = update_task(task_id, owner_user_id=user["user_id"], topic=enriched_topic, status="coordinating")
    background_tasks.add_task(
        generate_research_plan_task,
        task_id=task_id,
        topic=enriched_topic,
        locale=task["locale"],
    )

    return ResearchTaskResponse(
        task_id=task["task_id"],
        topic=task["topic"],
        locale=task["locale"],
        status=task["status"],
        current_step=task["current_step"] or 0,
        total_steps=task["total_steps"] or 0,
        clarification_questions=[],
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


@router.get("/{task_id}/agent-runs", response_model=list[AgentRunResponse])
async def get_agent_runs(task_id: str, user: dict = Depends(require_login)):
    """查看某个任务的 Agent 执行日志。"""
    if get_task(task_id, user_id=user["user_id"]) is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return list_agent_runs(task_id, user_id=user["user_id"])


@router.post("/{task_id}/confirm-plan")
async def confirm_plan(task_id: str, req: ConfirmPlanRequest, background_tasks: BackgroundTasks, user: dict = Depends(require_login)):
    """确认、拒绝或轻量修改研究计划。"""
    task = get_task(task_id, user_id=user["user_id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if req.action == "accept":
        if not task.get("plan_json"):
            raise HTTPException(status_code=400, detail="研究计划尚未生成")
        if task["status"] not in ("awaiting_confirmation", "failed"):
            raise HTTPException(status_code=400, detail=f"当前状态不能确认计划: {task['status']}")
        update_task(task_id, owner_user_id=user["user_id"], status="queued")
        background_tasks.add_task(execute_research_task, task_id=task_id)
        return {"status": "accepted", "task_id": task_id}
    elif req.action == "reject":
        update_task(task_id, owner_user_id=user["user_id"], status="failed")
        emitter = get_event_manager(task_id)
        await emitter.emit("error.fatal", message="用户取消了研究计划")
        remove_event_manager(task_id)
        return {"status": "rejected", "task_id": task_id}
    elif req.action == "edit":
        if not req.modified_steps:
            raise HTTPException(status_code=400, detail="edit 需要 modified_steps")
        import json
        from cli.models import ResearchPlan, ResearchStep

        plan = ResearchPlan.model_validate_json(task["plan_json"])
        plan.steps = [ResearchStep.model_validate(step) for step in req.modified_steps]
        update_task(
            task_id,
            owner_user_id=user["user_id"],
            plan_json=json.dumps(plan.model_dump(), ensure_ascii=False),
            total_steps=len(plan.steps),
        )
        return {"status": "edited", "task_id": task_id, "steps_count": len(plan.steps)}
    else:
        raise HTTPException(status_code=400, detail=f"无效的 action: {req.action}")


def _build_clarification_questions(topic: str) -> list[str]:
    """用低成本规则判断研究主题是否需要补充信息。"""
    text = topic.strip()
    normalized = text.lower()
    questions: list[str] = []

    broad_terms = {"分析", "研究", "调研", "趋势", "市场", "行业", "ai", "人工智能"}
    has_specific_object = len(text) >= 12 and text not in broad_terms
    has_focus = any(k in text for k in ("市场", "技术", "政策", "竞品", "用户", "商业", "投资", "风险", "趋势", "中国", "全球"))
    has_time = any(k in text for k in ("202", "最近", "近", "今年", "当前", "最新", "未来"))

    if len(text) < 8 or not has_specific_object:
        questions.append("你具体想研究哪个对象、行业、公司、技术或人群？")
    if not has_focus:
        questions.append("你更关注哪个维度：市场、技术、竞品、政策、投资、用户，还是风险？")
    if not has_time:
        questions.append("是否需要限定时间范围，例如最近一年、2026 年、近三年或最新动态？")
    if "竞品" in text and not any(k in normalized for k in ("vs", "对比", "竞争", "公司")):
        questions.append("是否有指定竞品或对比对象？")

    return questions[:3]
