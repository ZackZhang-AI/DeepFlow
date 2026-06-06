"""
PPT 排版 Agent — 将研究报告转化为幻灯片 Markdown
"""

import logging

from cli.config import Config
from cli.agents.base import LLMProvider
from cli.agents.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


async def compose_ppt(
    report_markdown: str,
    report_title: str,
    locale: str = "zh-CN",
) -> tuple[str, int, int]:
    """
    将研究报告转化为 PPT 幻灯片 Markdown。
    输出可直接用 marp / slidev / reveal.js 渲染。

    Returns:
        (slides_markdown, prompt_tokens, completion_tokens)
    """
    system_prompt = load_prompt("artifacts/ppt_composer", version=1)

    report_preview = report_markdown[:10000] if len(report_markdown) > 10000 else report_markdown

    user_message = f"""请将以下研究报告转化为 10-15 张幻灯片的演示文稿。

## 报告标题
{report_title}

## 报告内容
{report_preview}

## 输出语言
{"中文" if locale.startswith("zh") else "English"}

## 要求
- 10-15 张幻灯片
- 每张以 `## slide_title` 开头
- 用 `---` 分隔幻灯片
- 保持数据的准确性和引用的可追溯性
- 适合高管/客户演示场景"""

    response, pt, ct = await LLMProvider.generate_text(
        model=Config.PLANNER_MODEL,
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.2,
        max_tokens=4096,
    )

    return response, pt, ct
