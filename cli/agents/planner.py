"""
Planner Agent — 接收研究主题，生成结构化研究计划

模型: DeepSeek V4-Pro (deepseek-chat)
温度: 0.1 (需要稳定的 JSON 输出)
"""

import logging
from datetime import datetime

from cli.config import Config
from cli.models import ResearchPlan
from cli.agents.base import LLMProvider
from cli.agents.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


async def generate_plan(
    topic: str,
    locale: str = "zh-CN",
    max_steps: int = 5,
    context: str = "",
) -> tuple[ResearchPlan, int, int]:
    """
    生成研究计划。

    Args:
        topic: 用户研究主题
        locale: 语言 (zh-CN | en-US)
        max_steps: 最大步骤数
        context: 额外上下文（如澄清对话历史）

    Returns:
        (ResearchPlan, prompt_tokens, completion_tokens)
    """
    system_prompt = load_prompt("planner")

    user_message = f"""研究主题：{topic}
当前时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
最大步骤数：{max_steps}
语言：{locale}
{context}

请分析以上研究主题，生成一个包含 {max_steps} 步以内的研究计划。"""

    result, raw, prompt_tokens, completion_tokens = await LLMProvider.generate_json(
        model=Config.PLANNER_MODEL,
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=ResearchPlan,
        temperature=0.1,
        max_tokens=2048,
        max_retries=2,
    )

    if result is None:
        logger.error(f"Planner JSON 解析失败，原始输出: {raw[:500]}")
        # 返回一个最小可用计划
        return (
            ResearchPlan(
                locale=locale,
                has_enough_context=True,
                thought="JSON 解析失败，使用默认计划",
                title=topic,
                steps=[
                    {
                        "title": f"研究 {topic}",
                        "description": f"收集关于 {topic} 的最新信息",
                        "need_search": True,
                        "step_type": "research",
                    }
                ],
            ),
            prompt_tokens,
            completion_tokens,
        )

    return result, prompt_tokens, completion_tokens
