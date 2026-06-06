"""
研究任务 API 路由
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks

from backend.app.models.schemas import (
    CreateResearchRequest,
    ResearchTaskResponse,
    ConfirmPlanRequest,
)
from backend.app.core.db import create_task, get_task, update_task, list_tasks
from backend.app.core.events import EventManager
from backend.app.services.research import execute_research_task

router = APIRouter(prefix="/api/research-tasks", tags=["research"])


@router.post("", response_model=ResearchTaskResponse, status_code=201)
async def create_research_task(
    req: CreateResearchRequest,
    background_tasks: BackgroundTasks,
):
    """创建研究任务并立即启动后台执行"""
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    # 创建数据库记录
    task = create_task(task_id, req.topic, req.locale)

    # 启动后台研究（不等待确认，直接跑全流程）
    background_tasks.add_task(
        execute_research_task,
        task_id=task_id,
        topic=req.topic,
        locale=req.locale,
    )

    return ResearchTaskResponse(
        task_id=task["task_id"],
        topic=task["topic"],
        locale=task["locale"],
        status=task["status"],
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


@router.get("/{task_id}", response_model=ResearchTaskResponse)
async def get_research_task(task_id: str):
    """查询研究任务状态"""
    task = get_task(task_id)
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
        created_at=task["created_at"],
        updated_at=task["updated_at"],
    )


@router.get("")
async def list_research_tasks(limit: int = 20, offset: int = 0):
    """获取任务列表"""
    tasks = list_tasks(limit=limit, offset=offset)
    return [
        ResearchTaskResponse(
            task_id=t["task_id"],
            topic=t["topic"],
            locale=t["locale"],
            status=t["status"],
            current_step=t["current_step"] or 0,
            total_steps=t["total_steps"] or 0,
            created_at=t["created_at"],
            updated_at=t["updated_at"],
        )
        for t in tasks
    ]


@router.post("/{task_id}/confirm-plan")
async def confirm_plan(task_id: str, req: ConfirmPlanRequest):
    """确认或修改研究计划（Phase 2 完整实现）"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if req.action == "accept":
        update_task(task_id, status="researching")
        return {"status": "accepted", "task_id": task_id}
    elif req.action == "reject":
        update_task(task_id, status="failed")
        return {"status": "rejected", "task_id": task_id}
    elif req.action == "edit":
        # Phase 2: 支持修改计划后重新执行
        return {"status": "edited", "task_id": task_id, "note": "Edit not yet fully implemented"}
    else:
        raise HTTPException(status_code=400, detail=f"无效的 action: {req.action}")
