"""
研究任务 API 路由
"""

import uuid
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from backend.app.models.schemas import (
    AgentRunResponse,
    ClarificationAnswerRequest,
    CreateResearchRequest,
    ResearchTaskResponse,
    ConfirmPlanRequest,
    UsageSummary,
)
from backend.app.repositories.research import (
    create_task,
    get_task,
    list_agent_runs,
    list_tasks,
    get_usage_summary,
    update_task,
)
from backend.app.core.auth import require_login
from backend.app.core.events import get_event_manager, remove_event_manager
from backend.app.core.rate_limit import check_rate_limit
from backend.app.core.runtime_config import research_task_rate_limit
from backend.app.core.readiness import require_research_providers
from backend.app.core.access import require_scope_access, require_task_access
from backend.app.core.events import get_last_event_sequence
from backend.app.core.job_queue import enqueue_job
from cli.config import Config
from cli.budget import budget_from_task, get_budget
from cli.pricing import PRICING_VERSION

router = APIRouter(prefix="/api/research-tasks", tags=["research"])


@router.post("", response_model=ResearchTaskResponse, status_code=201)
async def create_research_task(
    req: CreateResearchRequest,
    user: dict = Depends(require_login),
):
    """创建研究任务并启动后台计划生成，等待用户确认后执行。"""
    check_rate_limit("research.create", user["user_id"], research_task_rate_limit())
    require_research_providers()
    require_scope_access(
        user["user_id"],
        req.workspace_id,
        req.project_id,
        write=True,
    )
    budget = get_budget(req.budget_profile)
    max_steps = min(budget.max_steps, Config.MAX_STEPS)
    reporter_model = (
        Config.PLANNER_MODEL if budget.profile == "fast" else Config.REPORTER_MODEL
    )
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    # 创建数据库记录
    task = create_task(
        task_id,
        req.topic,
        req.locale,
        search_domains=req.search_domains,
        recency_days=req.recency_days,
        user_id=user["user_id"],
        workspace_id=req.workspace_id,
        project_id=req.project_id,
        budget_profile=budget.profile,
        max_steps=max_steps,
        max_search_calls_per_step=budget.max_search_calls_per_step,
        max_crawl_pages_per_step=budget.max_crawl_pages_per_step,
        max_tokens_budget=budget.max_tokens,
        search_depth=budget.search_depth,
        planner_model=Config.PLANNER_MODEL,
        researcher_model=Config.RESEARCHER_MODEL,
        reporter_model=reporter_model,
        pricing_version=PRICING_VERSION,
    )

    clarification_questions = _build_clarification_questions(req.topic)
    if clarification_questions:
        task = update_task(
            task_id,
            owner_user_id=user["user_id"],
            status="clarifying",
            clarification_json=json.dumps(clarification_questions, ensure_ascii=False),
        )
        return _task_response(task)

    # 先生成研究计划，等待用户确认后再跑研究链路
    enqueue_job(
        "research_plan",
        task_id=task_id,
        user_id=user["user_id"],
        payload={"topic": req.topic, "locale": req.locale, "max_steps": max_steps},
    )

    return _task_response(task)


@router.get("/usage-summary", response_model=UsageSummary)
async def usage_summary(user: dict = Depends(require_login)):
    return UsageSummary.model_validate(get_usage_summary(user["user_id"]))


@router.get("/{task_id}", response_model=ResearchTaskResponse)
async def get_research_task(task_id: str, user: dict = Depends(require_login)):
    """查询研究任务状态"""
    task = require_task_access(task_id, user["user_id"])
    return _task_response(task)


@router.get("")
async def list_research_tasks(limit: int = 20, offset: int = 0, user: dict = Depends(require_login)):
    """获取任务列表"""
    tasks = list_tasks(limit=limit, offset=offset, user_id=user["user_id"])
    return [_task_response(task) for task in tasks]


@router.post("/{task_id}/clarifications", response_model=ResearchTaskResponse)
async def answer_clarifications(
    task_id: str,
    req: ClarificationAnswerRequest,
    user: dict = Depends(require_login),
):
    """提交澄清回答，并启动计划生成。"""
    task = require_task_access(task_id, user["user_id"], write=True)
    if task["status"] != "clarifying":
        raise HTTPException(status_code=400, detail=f"当前状态不需要澄清: {task['status']}")

    answers = [v.strip() for v in req.answers.values() if v.strip()]
    enriched_topic = task["topic"]
    if answers:
        enriched_topic += "\n\n用户补充信息：\n" + "\n".join(f"- {answer}" for answer in answers)

    task = update_task(task_id, topic=enriched_topic, status="coordinating")
    enqueue_job(
        "research_plan",
        task_id=task_id,
        user_id=user["user_id"],
        payload={
            "topic": enriched_topic,
            "locale": task["locale"],
            "max_steps": int(task.get("max_steps") or Config.MAX_STEPS),
        },
    )

    return _task_response(task)


@router.get("/{task_id}/agent-runs", response_model=list[AgentRunResponse])
async def get_agent_runs(task_id: str, user: dict = Depends(require_login)):
    """查看某个任务的 Agent 执行日志。"""
    task = require_task_access(task_id, user["user_id"])
    return list_agent_runs(task_id, user_id=task["user_id"])


@router.post("/{task_id}/confirm-plan")
async def confirm_plan(task_id: str, req: ConfirmPlanRequest, user: dict = Depends(require_login)):
    """确认、拒绝或轻量修改研究计划。"""
    task = require_task_access(task_id, user["user_id"], write=True)

    if req.action == "accept":
        if not task.get("plan_json"):
            raise HTTPException(status_code=400, detail="研究计划尚未生成")
        if task["status"] not in ("awaiting_confirmation", "failed"):
            raise HTTPException(status_code=400, detail=f"当前状态不能确认计划: {task['status']}")
        update_task(task_id, status="queued")
        enqueue_job("research_execute", task_id=task_id, user_id=user["user_id"])
        return {"status": "accepted", "task_id": task_id}
    elif req.action == "reject":
        update_task(task_id, status="failed")
        emitter = get_event_manager(task_id)
        await emitter.emit("error.fatal", message="用户取消了研究计划")
        remove_event_manager(task_id)
        return {"status": "rejected", "task_id": task_id}
    elif req.action == "edit":
        if not req.modified_steps:
            raise HTTPException(status_code=400, detail="edit 需要 modified_steps")
        import json
        from cli.models import ResearchPlan, ResearchStep

        budget = budget_from_task(task)
        if len(req.modified_steps) > budget.max_steps:
            raise HTTPException(
                status_code=422,
                detail=f"{budget.profile} 预算最多允许 {budget.max_steps} 个研究步骤",
            )
        plan = ResearchPlan.model_validate_json(task["plan_json"])
        plan.steps = [ResearchStep.model_validate(step) for step in req.modified_steps]
        update_task(
            task_id,
            plan_json=json.dumps(plan.model_dump(), ensure_ascii=False),
            total_steps=len(plan.steps),
        )
        return {"status": "edited", "task_id": task_id, "steps_count": len(plan.steps)}
    else:
        raise HTTPException(status_code=400, detail=f"无效的 action: {req.action}")


@router.post("/{task_id}/retry")
async def retry_research_task(task_id: str, user: dict = Depends(require_login)):
    task = require_task_access(task_id, user["user_id"], write=True)
    if task["status"] != "failed":
        raise HTTPException(status_code=409, detail="只有失败任务可以重试")
    if not task.get("retryable"):
        raise HTTPException(status_code=409, detail="该失败需要修改配置或计划后再执行")

    if task.get("plan_json"):
        job_type = "research_execute"
        payload = {}
    else:
        job_type = "research_plan"
        payload = {"topic": task["topic"], "locale": task["locale"]}
    update_task(
        task_id,
        status="queued",
        error_code="",
        error_message="",
    )
    enqueue_job(job_type, task_id=task_id, user_id=user["user_id"], payload=payload)
    return {"status": "queued", "task_id": task_id}


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


def _task_response(task: dict) -> ResearchTaskResponse:
    current_step = int(task.get("current_step") or 0)
    total_steps = int(task.get("total_steps") or 0)
    status = task.get("status") or "coordinating"
    progress = 100.0 if status == "completed" else (
        min(95.0, current_step / total_steps * 100) if total_steps else 0.0
    )
    plan = json.loads(task["plan_json"]) if task.get("plan_json") else None
    budget = budget_from_task(task)
    total_tokens = int(task.get("tokens_used") or 0)
    budget_percent = (
        min(100.0, total_tokens / budget.max_tokens * 100)
        if budget.max_tokens > 0
        else 0.0
    )
    return ResearchTaskResponse(
        task_id=task["task_id"],
        topic=task["topic"],
        locale=task["locale"],
        status=status,
        phase=task.get("failed_phase") or status,
        progress=progress,
        current_step=current_step,
        total_steps=total_steps,
        report_id=f"rep_{task['task_id']}" if task.get("report_markdown") else None,
        clarification_questions=json.loads(task.get("clarification_json") or "[]"),
        retryable=bool(task.get("retryable")),
        error_code=task.get("error_code") or "",
        error_message=task.get("error_message") or "",
        last_event_seq=get_last_event_sequence(task["task_id"]),
        plan=plan,
        budget=budget.model_dump(),
        usage={
            "prompt_tokens": int(task.get("prompt_tokens") or 0),
            "completion_tokens": int(task.get("completion_tokens") or 0),
            "total_tokens": total_tokens,
            "estimated_cost_rmb": float(task.get("cost_rmb") or 0.0),
            "search_calls": int(task.get("search_calls") or 0),
            "crawl_calls": int(task.get("crawl_calls") or 0),
            "search_credits": int(task.get("search_credits") or 0),
            "planner_model": task.get("planner_model") or Config.PLANNER_MODEL,
            "researcher_model": task.get("researcher_model") or Config.RESEARCHER_MODEL,
            "reporter_model": task.get("reporter_model") or Config.REPORTER_MODEL,
            "pricing_version": task.get("pricing_version") or PRICING_VERSION,
        },
        budget_percent=round(budget_percent, 1),
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )
