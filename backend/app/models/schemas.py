"""
API 请求/响应 Schema (Pydantic)
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=256)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class UserResponse(BaseModel):
    user_id: str
    username: str
    created_at: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: UserResponse


# ============================================================
# 研究任务
# ============================================================

class CreateResearchRequest(BaseModel):
    """创建研究任务"""
    topic: str = Field(..., min_length=1, max_length=500, description="研究主题")
    locale: str = Field(default="zh-CN", description="语言")
    max_steps: int = Field(default=5, ge=2, le=8, description="最大步骤数")
    search_domains: list[str] = Field(default_factory=list, description="优先或限定搜索域名")
    recency_days: Optional[int] = Field(default=None, ge=1, le=3650, description="优先检索最近 N 天内容")


class ResearchTaskResponse(BaseModel):
    """研究任务状态"""
    task_id: str
    topic: str
    locale: str
    status: str  # coordinating | clarifying | planning | awaiting_confirmation | researching | generating_report | completed | failed
    current_step: int = 0
    total_steps: int = 0
    report_id: Optional[str] = None
    clarification_questions: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ClarificationAnswerRequest(BaseModel):
    """提交澄清问题回答，并启动计划生成。"""
    answers: dict[str, str] = Field(default_factory=dict)


class ConfirmPlanRequest(BaseModel):
    """确认/修改研究计划"""
    action: str = Field(..., description="accept | edit | reject")
    modified_steps: Optional[list[dict]] = Field(default=None, description="修改后的步骤")


class AgentRunResponse(BaseModel):
    """Agent 执行日志。"""
    run_id: str
    task_id: str
    user_id: str = ""
    agent_name: str
    phase: str
    status: str
    input_summary: str = ""
    output_summary: str = ""
    tool_calls_json: str = "[]"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    elapsed_seconds: float = 0.0
    error: str = ""
    created_at: str


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


class SaveReportRequest(BaseModel):
    """保存报告编辑"""
    content_markdown: str = Field(..., min_length=1, description="完整 Markdown 报告")
    change_note: str = Field(default="手动编辑", description="版本说明")


class RewriteRequest(BaseModel):
    """报告重写请求"""
    section: str = Field(default="", description="要重写的报告部分")
    instruction: str = Field(..., description="重写指令")


class KnowledgeDocumentRequest(BaseModel):
    """新增知识库文档"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    source_name: str = ""
    source_type: str = "text"


class KnowledgeDocumentResponse(BaseModel):
    doc_id: str
    title: str
    source_name: str = ""
    source_type: str = "text"
    content_length: int = 0
    status: str = "pending"
    chunk_count: int = 0
    error_message: str = ""
    created_at: str
    updated_at: str


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
