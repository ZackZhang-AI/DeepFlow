"""
Prompt 加载器 — 从 prompts/ 目录加载 Agent 系统提示词
"""

from pathlib import Path
from datetime import datetime

from cli.config import Config


def load_prompt(agent_name: str, version: int = 1) -> str:
    """
    加载 Agent 的系统提示词。
    文件命名: prompts/{agent_name}@v{version}.md

    支持 {{ VARIABLE }} 模板替换:
    - {{ CURRENT_TIME }} → 当前时间
    """
    prompt_path = Config.PROMPTS_DIR / f"{agent_name}@v{version}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {prompt_path}")

    raw = prompt_path.read_text(encoding="utf-8")

    # 模板变量替换
    return raw.replace("{{ CURRENT_TIME }}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def render_user_message(template: str, **kwargs) -> str:
    """
    渲染用户消息模板。
    支持 {{ variable }} 语法。
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"{{{{ {key} }}}}", str(value))
    return result
