"""
Coder Agent — 执行数据处理步骤，编写并运行 Python 代码

模型: DeepSeek V4-Pro
核心约束:
  1. 必须通过代码验证计算结果
  2. 最多自动修复 3 次
  3. 不能执行危险操作
"""

import logging
from datetime import datetime

from cli.config import Config
from cli.models import ResearchFinding, ResearchStep, SourceReference, SourceType
from cli.agents.base import LLMProvider
from cli.agents.prompt_loader import load_prompt
from cli.tools.sandbox import execute_python, SandboxResult

logger = logging.getLogger(__name__)


async def process_step(
    step: ResearchStep,
    step_index: int,
    total_steps: int,
    locale: str = "zh-CN",
) -> tuple[ResearchFinding, int, int]:
    """
    执行单个数据处理步骤。

    流程:
    1. LLM 分析问题并编写代码
    2. 安全扫描 + 沙箱执行
    3. 如果失败，将错误反馈给 LLM 修复（最多 3 次）
    4. LLM 分析执行结果

    Returns:
        (ResearchFinding, total_prompt_tokens, total_completion_tokens)
    """
    total_prompt = 0
    total_completion = 0
    system_prompt = load_prompt("coder")
    artifacts: list[str] = []

    user_message = f"""## 数据处理任务
{step.description}

## 当前时间
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 输出语言
{"中文" if locale == "zh-CN" else "English"}

请按照 Coder Agent 的工作流程：分析问题 → 编写代码 → 执行 → 分析结果。"""

    max_attempts = Config.MAX_RETRIES + 1  # 1 次初始 + N 次重试
    code = ""
    last_result: SandboxResult | None = None

    for attempt in range(max_attempts):
        is_retry = attempt > 0

        if is_retry and last_result:
            user_message = f"""{user_message}

## 上次执行失败 (尝试 {attempt}/{max_attempts-1})

错误信息：
{last_result.error}

标准错误输出：
{last_result.stderr[:1000]}

请分析错误原因，修正代码后重新执行。"""

        # Step 1: LLM 生成代码 + 分析
        response, pt, ct = await LLMProvider.generate_text(
            model=Config.RESEARCHER_MODEL,  # Coder 使用 Researcher 同款模型
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.1,
            max_tokens=4096,
        )
        total_prompt += pt
        total_completion += ct

        # Step 2: 提取代码块
        code = _extract_code_block(response)
        if not code:
            if attempt < max_attempts - 1:
                user_message = f"{user_message}\n\n请在你的回答中包含 ```python 代码块。"
                continue
            else:
                logger.warning("未能提取 Python 代码块")
                break

        # Step 3: 沙箱执行
        result = await execute_python(code, timeout=30)
        last_result = result

        if result.success:
            break  # 执行成功，跳出重试循环

        # 如果是安全检查失败，不需要重试代码
        if "安全检查失败" in result.error:
            break

        logger.info(f"  Coder 执行失败 (attempt {attempt+1}/{max_attempts}): {result.error[:100]}")

    # Step 4: 生成最终分析
    if last_result and (last_result.success or "安全检查失败" in (last_result.error or "")):
        final_response = response  # 使用首次 LLM 输出（已包含分析）
    else:
        # 需要 LLM 分析失败的最终结果
        final_prompt = f"""{response}

## 最终执行结果
{'成功' if last_result and last_result.success else '失败'}

标准输出:
{last_result.stdout[:3000] if last_result else ''}

错误:
{last_result.error if last_result else '未知错误'}

请基于以上结果，给出最终的问题分析、执行结果和结论。"""

        final_response, pt, ct = await LLMProvider.generate_text(
            model=Config.RESEARCHER_MODEL,
            system_prompt=system_prompt,
            user_message=final_prompt,
            temperature=0.1,
            max_tokens=2048,
        )
        total_prompt += pt
        total_completion += ct

    # 构建 ResearchFinding
    finding = ResearchFinding(
        step_id=f"step_{step_index}",
        step_title=step.title,
        problem_statement=step.description,
        findings_markdown=f"{final_response}\n\n### 执行代码\n```python\n{code[:2000]}\n```\n\n### 执行输出\n```\n{(last_result.stdout if last_result else '')[:2000]}\n```",
        conclusion=_extract_conclusion(final_response),
        references=[],  # Coder 一般不需要外部引用
    )

    return finding, total_prompt, total_completion


def _extract_code_block(text: str) -> str:
    """从 LLM 输出中提取 Python 代码块"""
    import re

    # 匹配 ```python ... ```
    match = re.search(r"```(?:python|py)\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 匹配 ``` ... ``` (无语言标注)
    match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        # 基本判断：包含 Python 关键字
        if any(kw in code for kw in ["import ", "def ", "print(", "for ", "if __name__"]):
            return code

    return ""


def _extract_conclusion(text: str) -> str:
    """从 Coder 输出中提取结论"""
    import re

    # 尝试提取 Analysis 部分
    match = re.search(r"## Analysis\n+(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if match:
        return match.group(1).strip()[:1000]

    # 取最后一段
    paragraphs = text.split("\n\n")
    return paragraphs[-1][:500] if paragraphs else ""
