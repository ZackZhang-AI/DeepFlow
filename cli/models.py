"""
DeepFlow 数据模型 (Pydantic)

所有 Agent 的输入/输出 Schema 定义。
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# 研究计划
# ============================================================

class StepType(str, Enum):
    RESEARCH = "research"
    PROCESSING = "processing"


class ResearchStep(BaseModel):
    """单个研究步骤"""
    title: str = Field(..., description="步骤标题")
    description: str = Field(..., description="步骤详细描述，说明需要研究什么")
    need_search: bool = Field(..., description="是否需要联网搜索")
    step_type: StepType = Field(..., description="步骤类型")


class ResearchPlan(BaseModel):
    """研究计划"""
    locale: str = Field(default="zh-CN", description="语言")
    has_enough_context: bool = Field(default=True, description="上下文是否足够制定计划")
    thought: str = Field(default="", description="Planner 的思考过程")
    title: str = Field(..., description="研究报告标题")
    steps: list[ResearchStep] = Field(default_factory=list, description="研究步骤列表")


# ============================================================
# 来源引用
# ============================================================

class SourceType(str, Enum):
    WEB = "web"
    KNOWLEDGE_BASE = "knowledge_base"
    DOCUMENT = "document"


class SourceReference(BaseModel):
    """引用来源"""
    title: str = Field(..., description="来源标题")
    url: str = Field(..., description="来源 URL")
    source_type: SourceType = Field(default=SourceType.WEB, description="来源类型")
    snippet: str = Field(default="", description="内容摘要")
    published_at: Optional[str] = Field(default=None, description="发布时间")
    retrieved_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="获取时间")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="可信度 0-1")


# ============================================================
# 研究发现
# ============================================================

class ResearchFinding(BaseModel):
    """单个步骤的研究发现"""
    step_id: str = Field(..., description="步骤 ID")
    step_title: str = Field(default="", description="步骤标题")
    problem_statement: str = Field(..., description="研究问题")
    findings_markdown: str = Field(..., description="研究发现 (Markdown)")
    conclusion: str = Field(..., description="结论")
    references: list[SourceReference] = Field(default_factory=list, description="引用来源")


# ============================================================
# 搜索相关
# ============================================================

class SearchResult(BaseModel):
    """单条搜索结果"""
    title: str
    url: str
    snippet: str
    published_at: Optional[str] = None
    source: str = "tavily"  # tavily | serpapi


class CrawlResult(BaseModel):
    """网页抓取结果"""
    url: str
    title: str
    content: str  # 提取的正文 (Markdown)
    raw_text_length: int = 0
    success: bool = True
    error: Optional[str] = None


# ============================================================
# 使用统计
# ============================================================

class UsageStats(BaseModel):
    """一次研究任务的使用统计"""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    search_calls: int = 0
    crawl_calls: int = 0
    cost_estimate_rmb: float = 0.0
    elapsed_seconds: float = 0.0
    retries: int = 0


class RunRecord(BaseModel):
    """一次研究的完整记录"""
    run_id: str
    topic: str
    locale: str = "zh-CN"
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    plan: Optional[ResearchPlan] = None
    findings: list[ResearchFinding] = Field(default_factory=list)
    report_markdown: str = ""
    usage: UsageStats = Field(default_factory=UsageStats)
    errors: list[str] = Field(default_factory=list)
    status: str = "init"  # init | planning | researching | reporting | completed | failed
