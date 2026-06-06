"""
Agent 基类 — 封装 LLM 调用
"""

import json
import time
from typing import Optional, Type, TypeVar
from openai import OpenAI
from pydantic import BaseModel

from cli.config import Config

T = TypeVar("T", bound=BaseModel)


class LLMProvider:
    """统一的 LLM 调用接口，支持 DeepSeek 和阿里百炼"""

    @staticmethod
    def get_client(model: str) -> tuple[OpenAI, str]:
        """
        根据模型名返回对应的 client 和实际 model id。
        规则：
        - deepseek 开头 → DeepSeek API
        - qwen 开头 → 阿里百炼 DashScope API
        """
        if model.startswith("deepseek"):
            return (
                OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_BASE_URL),
                model,
            )
        elif model.startswith("qwen"):
            return (
                OpenAI(
                    api_key=Config.DASHSCOPE_API_KEY,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                ),
                model,
            )
        else:
            # 默认走 DeepSeek
            return (
                OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_BASE_URL),
                model,
            )

    @staticmethod
    async def generate_text(
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> tuple[str, int, int]:
        """
        调用 LLM 生成文本。
        返回 (文本内容, prompt_tokens, completion_tokens)
        """
        client, model_id = LLMProvider.get_client(model)

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        return content, prompt_tokens, completion_tokens

    @staticmethod
    async def generate_json(
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        max_retries: int = 2,
    ) -> tuple[Optional[T], str, int, int]:
        """
        调用 LLM 生成结构化 JSON。
        返回 (Pydantic 对象或 None, 原始文本, prompt_tokens, completion_tokens)

        内置 JSON 修复：如果首次输出不合法，将错误信息反馈给模型重试。
        """
        client, model_id = LLMProvider.get_client(model)

        # 构造带有 JSON Schema 要求的 user message
        schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False, indent=2)
        full_message = f"""{user_message}

请严格按照以下 JSON Schema 输出，只输出 JSON，不要包含任何其他文字：
```json
{schema_json}
```

重要：
- 只输出 JSON 对象，不要用 markdown 代码块包裹
- 所有字段必须填写，不要省略
- 字符串使用双引号"""

        last_error = None
        for attempt in range(max_retries + 1):
            if attempt > 0:
                full_message = f"""{user_message}

请严格按照以下 JSON Schema 输出。

上次输出解析失败，错误信息：
{last_error}

请修正后重新输出 JSON：
```json
{schema_json}
```"""

            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            raw = response.choices[0].message.content or ""
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0

            # 尝试提取 JSON
            try:
                # 处理可能被 markdown 代码块包裹的情况
                json_str = raw.strip()
                if json_str.startswith("```"):
                    lines = json_str.split("\n")
                    json_str = "\n".join(lines[1:-1])
                parsed = response_model.model_validate_json(json_str)
                return parsed, raw, prompt_tokens, completion_tokens
            except Exception as e:
                last_error = str(e)
                continue

        return None, raw, prompt_tokens, completion_tokens
