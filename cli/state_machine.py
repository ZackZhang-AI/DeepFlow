"""
研究流程状态机 — 驱动整个 Agent 协作流程

状态流转:
  INIT → PLANNING → AWAITING_CONFIRMATION → RESEARCHING → REPORTING → COMPLETED
  任何阶段都可能 → FAILED
"""

import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from pathlib import Path

from cli.config import Config
from cli.models import ResearchPlan, ResearchFinding, ResearchStep, RunRecord, UsageStats
from cli.agents.planner import generate_plan
from cli.agents.researcher import research_step
from cli.agents.coder import process_step
from cli.agents.reporter import generate_report

logger = logging.getLogger(__name__)


class ResearchState(str, Enum):
    INIT = "init"
    PLANNING = "planning"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RESEARCHING = "researching"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchStateMachine:
    """
    研究流程状态机。

    用法:
        sm = ResearchStateMachine(topic="分析 AI 趋势")
        sm.on_plan_ready = lambda plan: print(plan)  # 回调让用户确认
        report = await sm.run()
    """

    def __init__(self, topic: str, locale: str = "zh-CN"):
        self.topic = topic
        self.locale = locale
        self.state = ResearchState.INIT

        # 上下文数据
        self.plan: ResearchPlan | None = None
        self.findings: list[ResearchFinding] = []
        self.report_markdown: str = ""

        # 统计
        self.usage = UsageStats()
        self.errors: list[str] = []
        self.started_at = time.time()

        # 回调
        self.on_plan_ready: callable | None = None  # async (plan) -> "accept"|"edit"|"reject"
        self.on_progress: callable | None = None  # async (state, message) -> None

    async def run(self) -> RunRecord:
        """执行完整研究流程"""
        run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")

        try:
            # ---- Phase 1: Planning ----
            await self._emit_progress("planning", "正在分析研究主题，生成研究计划...")
            self.state = ResearchState.PLANNING

            plan, pt, ct = await generate_plan(
                topic=self.topic,
                locale=self.locale,
                max_steps=Config.MAX_STEPS,
            )
            self._add_tokens(Config.PLANNER_MODEL, pt, ct, 0.004)  # V4-Pro ¥0.004/1K tokens average
            self._ensure_token_budget()
            self.plan = plan

            await self._emit_progress("plan_created", f"研究计划已生成: {plan.title}")

            # ---- Phase 2: Human Confirmation ----
            self.state = ResearchState.AWAITING_CONFIRMATION

            if self.on_plan_ready:
                action = await self.on_plan_ready(plan)
                if action == "reject":
                    self.state = ResearchState.FAILED
                    self.errors.append("用户拒绝了研究计划")
                    return self._build_record(run_id)
                elif action == "edit":
                    # 用户编辑了计划 —— 用户应该在回调中修改 self.plan
                    await self._emit_progress("plan_edited", "计划已更新")
            else:
                # 无回调时自动接受
                logger.info("无确认回调，自动接受计划")

            # ---- Phase 3: Researching ----
            self.state = ResearchState.RESEARCHING
            await self._emit_progress("research_started", f"开始执行 {len(plan.steps)} 个研究步骤...")

            for i, step in enumerate(plan.steps):
                step_num = i + 1
                step_label = f"[{step_num}/{len(plan.steps)}]"

                if step.need_search:
                    await self._emit_progress("step_started", f"{step_label} [搜索] {step.title}")
                    finding, pt, ct = await research_step(
                        step=step, step_index=step_num,
                        total_steps=len(plan.steps), locale=self.locale,
                    )
                    self._add_tokens(Config.RESEARCHER_MODEL, pt, ct, 0.004)
                else:
                    await self._emit_progress("step_started", f"{step_label} [计算] {step.title}")
                    logger.info(f"  Coder 处理步骤: {step.title}")
                    finding, pt, ct = await process_step(
                        step=step, step_index=step_num,
                        total_steps=len(plan.steps), locale=self.locale,
                        previous_findings=self.findings,
                    )
                    self._add_tokens(Config.RESEARCHER_MODEL, pt, ct, 0.004)
                self.usage.search_calls += finding.search_calls
                self.usage.crawl_calls += finding.crawl_calls
                self._ensure_token_budget()
                self.findings.append(finding)

                await self._emit_progress(
                    "step_completed",
                    f"[{i+1}/{len(plan.steps)}] 完成: {step.title} ({len(finding.references)} 个来源)",
                )

            if not self.findings:
                self.state = ResearchState.FAILED
                self.errors.append("所有研究步骤均未产生有效发现")
                return self._build_record(run_id)

            # ---- Phase 4: Reporting ----
            self._ensure_token_budget()
            self.state = ResearchState.REPORTING
            await self._emit_progress("report_started", "正在生成研究报告...")

            report, pt, ct = await generate_report(
                plan=plan,
                findings=self.findings,
                locale=self.locale,
            )
            self._add_tokens(Config.REPORTER_MODEL, pt, ct, 0.008)  # Reporter 可能用更贵模型
            self._ensure_token_budget()
            self.report_markdown = report

            # ---- Done ----
            self.state = ResearchState.COMPLETED
            await self._emit_progress("completed", "研究报告生成完毕！")

            return self._build_record(run_id)

        except Exception as e:
            self.state = ResearchState.FAILED
            self.errors.append(str(e))
            logger.exception(f"研究流程异常: {e}")
            return self._build_record(run_id)

    def _add_tokens(self, model: str, prompt: int, completion: int, price_per_1k: float):
        """累加 token 统计"""
        self.usage.prompt_tokens += prompt
        self.usage.completion_tokens += completion
        self.usage.total_tokens += prompt + completion
        self.usage.model = model
        # 粗略费用估算
        total_1k = (prompt + completion) / 1000.0
        self.usage.cost_estimate_rmb += total_1k * price_per_1k

    def _ensure_token_budget(self):
        """超过预算时中断，防止任务无声烧钱。"""
        if Config.MAX_TOKEN_BUDGET <= 0:
            return
        if self.usage.total_tokens > Config.MAX_TOKEN_BUDGET:
            raise RuntimeError(
                f"Token 预算超限: {self.usage.total_tokens} > {Config.MAX_TOKEN_BUDGET}"
            )

    async def _emit_progress(self, event: str, message: str):
        """触发进度回调"""
        logger.info(f"[{event}] {message}")
        if self.on_progress:
            await self.on_progress(event, message)

    def _build_record(self, run_id: str) -> RunRecord:
        """构建 RunRecord"""
        self.usage.elapsed_seconds = time.time() - self.started_at
        return RunRecord(
            run_id=run_id,
            topic=self.topic,
            locale=self.locale,
            plan=self.plan,
            findings=self.findings,
            report_markdown=self.report_markdown,
            usage=self.usage,
            errors=self.errors,
            status=self.state.value,
        )

    async def continue_after_confirmation(self, confirmed_plan: ResearchPlan = None):
        """
        在用户确认计划后继续执行。
        由外部调用（例如 CLI 或 Web API 在收到用户确认后）。
        """
        if confirmed_plan:
            self.plan = confirmed_plan
        # 继续从 researching 阶段执行
        # ... （这部分逻辑与 run() 中的 Phase 3/4 相同，实际使用时提取公共方法）
