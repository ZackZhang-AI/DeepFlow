"""
API 请求/响应 Schema (Pydantic)
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# 研究任务
# ============================================================

class CreateResearchRequest(BaseModel):
    """创建研究任务"""
    topic: str = Field(..., min_length=1, max_length=500, description="研究主题")
    locale: str = Field(default="zh-CN", description="语言")
    max_steps: int = Field(default=5, ge=2, le=8, description="最大步骤数")


class ResearchTaskResponse(BaseModel):
    """研究任务状态"""
    task_id: str
    topic: str
    locale: str
    status: str  # coordinating | clarifying | planning | awaiting_confirmation | researching | generating_report | completed | failed
    current_step: int = 0
    total_steps: int = 0
    report_id: Optional[str] = None
    created_at: str
    updated_at: str


class ConfirmPlanRequest(BaseModel):
    """确认/修改研究计划"""
    action: str = Field(..., description="accept | edit | reject")
    modified_steps: Optional[list[dict]] = Field(default=None, description="修改后的步骤")


class ResearchEvent(BaseModel):
    """研究进度事件（SSE）"""
    type: str  # planner.completed | step.started | step.completed | tool.called | report.started | report.completed | error
    data: dict = Field(default_factory=dict)


# ============================================================
# 报告
# ============================================================

class ReportResponse(BaseModel):
    """报告"""
    report_id: str
    task_id: str
    title: str
    content_markdown: str
    sources_count: int
    tokens_used: int
    cost_rmb: float
    elapsed_seconds: float
    created_at: str


class RewriteRequest(BaseModel):
    """报告重写请求"""
    section: str = Field(..., description="要重写的报告部分")
    instruction: str = Field(..., description="重写指令")


# ============================================================
# 统计
# ============================================================

class TaskStats(BaseModel):
    """任务统计"""
    total_tasks: int
    completed: int
    failed: int
    avg_tokens: float
    avg_cost_rmb: float
    avg_elapsed_seconds: float
