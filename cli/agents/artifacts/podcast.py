"""
播客脚本 Agent — 将报告转化为双人对话脚本
"""

import json
import logging
from pydantic import BaseModel

from cli.config import Config
from cli.agents.base import LLMProvider
from cli.agents.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class ScriptLine(BaseModel):
    speaker: str  # "male" | "female"
    paragraph: str


class PodcastScript(BaseModel):
    locale: str  # "zh" | "en"
    title: str
    lines: list[ScriptLine]


async def generate_podcast_script(
    report_markdown: str,
    report_title: str,
    locale: str = "zh-CN",
) -> tuple[PodcastScript | None, int, int]:
    """
    将研究报告转化为播客脚本。

    Returns:
        (PodcastScript, prompt_tokens, completion_tokens)
    """
    system_prompt = load_prompt("artifacts/podcast_script", version=1)

    # 截断过长的报告，留足够上下文
    report_preview = report_markdown[:8000] if len(report_markdown) > 8000 else report_markdown

    user_message = f"""请将以下研究报告转化为一段 10 段左右的播客对话脚本。

## 报告标题
{report_title}

## 报告内容
{report_preview}

## 输出语言
{"中文" if locale.startswith("zh") else "English"}

请输出 JSON，不要用 markdown 包裹。"""

    result, raw, pt, ct = await LLMProvider.generate_json(
        model=Config.PLANNER_MODEL,  # 使用较强的模型保证 JSON 质量
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=PodcastScript,
        temperature=0.4,
        max_tokens=4096,
        max_retries=2,
    )

    if result is None:
        logger.warning(f"Podcast JSON 解析失败，尝试提取: {raw[:200]}")
        return None, pt, ct

    return result, pt, ct


def format_script_for_display(script: PodcastScript) -> str:
    """将脚本格式化为可读的 Markdown"""
    lines: list[str] = [f"# {script.title}\n"]
    speaker_names = {"male": "🎙️ 主持人", "female": "🎤 嘉宾"}

    for line in script.lines:
        name = speaker_names.get(line.speaker, line.speaker)
        lines.append(f"**{name}**: {line.paragraph}\n")

    return "\n".join(lines)
