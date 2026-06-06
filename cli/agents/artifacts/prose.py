"""
文本操作 Agent — 润色、扩展、精简

三个独立函数，共享相似接口。
"""

import logging

from cli.config import Config
from cli.agents.base import LLMProvider
from cli.agents.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


async def improve_text(text: str, instruction: str = "") -> tuple[str, int, int]:
    """
    润色文本：修正语法、优化表达、改善可读性。

    Args:
        text: 待润色的文本
        instruction: 额外润色指令（如"用更正式的语调"）

    Returns:
        (improved_text, prompt_tokens, completion_tokens)
    """
    system_prompt = load_prompt("artifacts/prose_improver", version=1)

    user_message = f"""请润色以下文本。

{instruction if instruction else '保持原意和准确性，优化表达流畅度。'}

---

{text}
---

只输出润色后的文本。"""

    return await LLMProvider.generate_text(
        model=Config.RESEARCHER_MODEL,
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.3,
        max_tokens=min(len(text) * 3, 4096),
    )


async def expand_text(text: str, target_ratio: float = 2.5) -> tuple[str, int, int]:
    """
    扩展文本：添加解释、例子、过渡，使内容更丰富。

    Args:
        text: 待扩展的文本
        target_ratio: 目标扩展比例 (2.0-3.0)

    Returns:
        (expanded_text, prompt_tokens, completion_tokens)
    """
    system_prompt = load_prompt("artifacts/prose_longer", version=1)

    target_words = int(len(text) * target_ratio)
    user_message = f"""请将以下文本扩展为约 {target_words} 字的版本。

---

{text}
---

只输出扩展后的文本。"""

    return await LLMProvider.generate_text(
        model=Config.RESEARCHER_MODEL,
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.4,
        max_tokens=min(target_words + 500, 4096),
    )


async def shorten_text(text: str, target_ratio: float = 0.4) -> tuple[str, int, int]:
    """
    精简文本：删除冗余、合并相似论点、保留核心信息。

    Args:
        text: 待精简的文本
        target_ratio: 目标压缩比例 (0.3-0.5)

    Returns:
        (shortened_text, prompt_tokens, completion_tokens)
    """
    system_prompt = load_prompt("artifacts/prose_shorter", version=1)

    target_words = int(len(text) * target_ratio)
    user_message = f"""请将以下文本压缩为约 {target_words} 字的版本，保留所有关键数据和结论。

---

{text}
---

只输出精简后的文本。"""

    # Prose shortener can use a cheaper model
    model = Config.RESEARCHER_MODEL

    return await LLMProvider.generate_text(
        model=model,
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.2,
        max_tokens=min(target_words + 500, 2048),
    )
