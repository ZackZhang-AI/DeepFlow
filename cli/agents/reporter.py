"""
Reporter Agent — 汇总所有研究发现，生成结构化 Markdown 报告

模型: DeepSeek V4-Pro 或 Qwen3.7-Max
核心约束:
  1. 只能使用 Researcher 提供的信息
  2. 不能编造任何事实
  3. 引用统一放到 Key Citations
  4. 信息不足时明确说明局限性
"""

import logging
from datetime import datetime

from cli.config import Config
from cli.models import ResearchFinding, ResearchPlan
from cli.agents.base import LLMProvider
from cli.agents.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


async def generate_report(
    plan: ResearchPlan,
    findings: list[ResearchFinding],
    locale: str = "zh-CN",
    report_style: str = "general",
    use_fallback_model: bool = False,
) -> tuple[str, int, int]:
    """
    生成最终研究报告，支持 6 种风格。

    Styles: general | academic | popular_science | news | social_media | strategic_investment
    """
    model = Config.REPORTER_FALLBACK_MODEL if use_fallback_model else Config.REPORTER_MODEL

    # 尝试加载 v2 prompt，失败则用 v1
    try:
        system_prompt = load_prompt("reporter", version=2)
    except FileNotFoundError:
        system_prompt = load_prompt("reporter", version=1)

    findings_text = _format_findings(findings)
    all_refs = _collect_references(findings)

    # 根据风格添加特定指令
    style_instructions = _get_style_instructions(report_style, locale)

    user_message = f"""## 研究主题
{plan.title}

## 研究计划
{_format_plan(plan)}

## 研究发现
{findings_text}

## 全部引用来源
{all_refs}

## 输出要求
- 报告语言：{"中文" if locale == "zh-CN" else "English"}
- 报告风格：{report_style}
- 当前日期：{datetime.now().strftime("%Y-%m-%d")}
- 所有引用统一放到 Key Citations 部分
- 如果需要展示对比数据，优先使用 Markdown 表格
{style_instructions}"""

    response, prompt_tokens, completion_tokens = await LLMProvider.generate_text(
        model=model,
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.3 if report_style != "strategic_investment" else 0.2,
        max_tokens=8192 if report_style != "strategic_investment" else 12000,
    )

    if (not response or len(response) < 200) and not use_fallback_model \
       and Config.DASHSCOPE_API_KEY and Config.REPORTER_FALLBACK_MODEL != Config.REPORTER_MODEL:
        logger.info("主模型输出过短，尝试备用模型...")
        return await generate_report(plan, findings, locale, report_style, use_fallback_model=True)

    return response, prompt_tokens, completion_tokens


def _get_style_instructions(style: str, locale: str) -> str:
    """获取风格专用指令"""
    instructions = {
        "academic": "\n".join([
            "- 使用学术论文风格：\"本文\" \"研究表明\" \"数据表明\"",
            "- 包含 Abstract(摘要) → Discussion → Conclusions 结构",
            "- 正文中内联引用来源",
            "- 避免口语化表达",
        ]),
        "popular_science": "\n".join([
            "- 科普风格：通俗易懂，用比喻和类比",
            "- 开篇用一个引人入胜的问题或现象引入",
            "- 复杂数据转为日常类比",
            "- 保持科学准确性",
        ]),
        "news": "\n".join([
            "- 新闻体：倒金字塔结构，最重要的信息在前",
            "- 包含 导语(Lead, 5W1H) → 新闻主体 → 编辑点评",
            "- 使用短段落、多小标题",
            "- 记者式客观中立",
        ]),
        "social_media": "\n".join([
            "- 小红书风格(中文)：emoji丰富、轻松活泼、分点简短",
            "- 使用\"姐妹们\"\"宝藏\"\"干货\"\"码住\"等用语",
            "- Twitter/X风格(英文)：Thread 1/N格式、#hashtag",
            "- 结尾引导互动",
        ]),
        "strategic_investment": "\n".join([
            "- 投资研究报告风格：10,000-15,000字",
            "- 必须包含：TRL评估、FTO专利分析、IRR预期回报率",
            "- 使用\"技术壁垒\"\"商业化路径\"\"竞争护城河\"等术语",
            "- 投资建议格式：\"投资评级 | 目标估值 | 投资窗口 | 预期IRR | 退出策略\"",
        ]),
        "general": "",
    }
    return instructions.get(style, "")


def _format_findings(findings: list[ResearchFinding]) -> str:
    """格式化为 Reporter 输入"""
    parts = []
    for i, f in enumerate(findings, 1):
        parts.append(f"### 步骤 {i}: {f.step_title}")
        parts.append(f"研究问题: {f.problem_statement}")
        parts.append(f"\n{f.findings_markdown}")
        parts.append(f"\n结论: {f.conclusion}")
        parts.append(f"\n引用数: {len(f.references)}")
        parts.append("\n---\n")
    return "\n".join(parts)


def _format_plan(plan: ResearchPlan) -> str:
    """格式化计划摘要"""
    lines = []
    for i, step in enumerate(plan.steps, 1):
        search_icon = "🔍" if step.need_search else "💻"
        lines.append(f"{i}. {search_icon} {step.title}")
    return "\n".join(lines)


def _collect_references(findings: list[ResearchFinding]) -> str:
    """收集所有唯一引用"""
    seen: set[str] = set()
    lines = []
    idx = 1
    for f in findings:
        for ref in f.references:
            if ref.url not in seen:
                seen.add(ref.url)
                lines.append(f"[{idx}] [{ref.title}]({ref.url})")
                idx += 1
    return "\n".join(lines)
