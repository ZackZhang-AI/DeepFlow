"""Minimal built-in tool registry for DeepFlow agents."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from backend.app.core.runtime_config import sandbox_tool_disabled
from backend.app.services.embedding import EmbeddingError
from backend.app.services.knowledge import search_knowledge_chunks
from cli.tools.sandbox import execute_python
from cli.tools.web_search import web_search


ToolHandler = Callable[[dict[str, Any], dict], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    name: str
    description: str
    category: str
    input_schema: dict[str, Any] = field(default_factory=dict)


_TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "web_search": ToolDefinition(
        tool_id="web_search",
        name="Web Search",
        category="research",
        description="Search the public web through the configured search provider.",
        input_schema={
            "query": "string, required",
            "max_results": "number, optional, default 5",
            "include_domains": "string[], optional",
            "recency_days": "number, optional",
        },
    ),
    "knowledge_search": ToolDefinition(
        tool_id="knowledge_search",
        name="Knowledge Search",
        category="knowledge",
        description="Search the current user's private knowledge base.",
        input_schema={
            "query": "string, required",
            "limit": "number, optional, default 5",
            "rerank": "boolean, optional",
        },
    ),
    "python_sandbox": ToolDefinition(
        tool_id="python_sandbox",
        name="Python Sandbox",
        category="code",
        description="Run safe Python snippets in the existing DeepFlow sandbox.",
        input_schema={
            "code": "string, required",
            "timeout": "number, optional, default 10",
        },
    ),
}

_enabled_tools: dict[str, bool] = {tool_id: True for tool_id in _TOOL_DEFINITIONS}


def _tool_enabled(tool_id: str) -> bool:
    if tool_id == "python_sandbox" and sandbox_tool_disabled():
        return False
    return _enabled_tools.get(tool_id, False)


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "tool_id": tool.tool_id,
            "name": tool.name,
            "description": tool.description,
            "category": tool.category,
            "enabled": _tool_enabled(tool.tool_id),
            "input_schema": tool.input_schema,
        }
        for tool in _TOOL_DEFINITIONS.values()
    ]


def get_tool(tool_id: str) -> dict[str, Any] | None:
    tool = _TOOL_DEFINITIONS.get(tool_id)
    if tool is None:
        return None
    return {
        "tool_id": tool.tool_id,
        "name": tool.name,
        "description": tool.description,
        "category": tool.category,
        "enabled": _tool_enabled(tool.tool_id),
        "input_schema": tool.input_schema,
    }


def set_tool_enabled(tool_id: str, enabled: bool) -> dict[str, Any] | None:
    if tool_id not in _TOOL_DEFINITIONS:
        return None
    _enabled_tools[tool_id] = enabled
    return get_tool(tool_id)


async def test_tool(tool_id: str, input_data: dict[str, Any], user: dict) -> dict[str, Any]:
    tool = _TOOL_DEFINITIONS.get(tool_id)
    if tool is None:
        raise ValueError("Tool not found")
    if not _tool_enabled(tool_id):
        return _result(False, "", "", 0.0, "Tool is disabled")

    started = time.perf_counter()
    try:
        if tool_id == "web_search":
            payload = await _test_web_search(input_data, user)
        elif tool_id == "knowledge_search":
            payload = await _test_knowledge_search(input_data, user)
        elif tool_id == "python_sandbox":
            payload = await _test_python_sandbox(input_data, user)
        else:
            payload = {"input_summary": "", "output_summary": "", "error": "Unsupported tool"}

        elapsed = time.perf_counter() - started
        return _result(
            success=not payload.get("error"),
            input_summary=payload.get("input_summary", ""),
            output_summary=payload.get("output_summary", ""),
            elapsed_seconds=elapsed,
            error=payload.get("error", ""),
            raw_output=payload.get("raw_output"),
        )
    except EmbeddingError as exc:
        return _result(False, _summarize_input(input_data), "", time.perf_counter() - started, str(exc))
    except Exception as exc:
        return _result(False, _summarize_input(input_data), "", time.perf_counter() - started, str(exc))


async def _test_web_search(input_data: dict[str, Any], _user: dict) -> dict[str, Any]:
    query = _required_text(input_data, "query")
    max_results = _bounded_int(input_data.get("max_results"), default=5, minimum=1, maximum=10)
    include_domains = input_data.get("include_domains") or []
    if not isinstance(include_domains, list):
        include_domains = []
    recency_days = input_data.get("recency_days")
    if recency_days is not None:
        recency_days = _bounded_int(recency_days, default=30, minimum=1, maximum=3650)

    results = await web_search(
        query=query,
        max_results=max_results,
        include_domains=[str(item) for item in include_domains],
        recency_days=recency_days,
    )
    summary = "\n".join(f"- {item.title}: {item.url}" for item in results[:max_results])
    return {
        "input_summary": f"query={query}; max_results={max_results}",
        "output_summary": summary or "No search results returned. Check search provider configuration.",
        "raw_output": [item.model_dump() for item in results],
    }


async def _test_knowledge_search(input_data: dict[str, Any], user: dict) -> dict[str, Any]:
    query = _required_text(input_data, "query")
    limit = _bounded_int(input_data.get("limit"), default=5, minimum=1, maximum=20)
    rerank = input_data.get("rerank")
    if rerank is not None:
        rerank = bool(rerank)

    hits = search_knowledge_chunks(query, limit=limit, use_rerank=rerank, user_id=user["user_id"])
    summary = "\n".join(
        f"- kb://{hit['doc_id']}#{hit['chunk_id']} score={hit.get('score', 0):.3f} {hit.get('preview', '')[:120]}"
        for hit in hits
    )
    return {
        "input_summary": f"query={query}; limit={limit}; rerank={rerank}",
        "output_summary": summary or "No matching knowledge chunks.",
        "raw_output": hits,
    }


async def _test_python_sandbox(input_data: dict[str, Any], _user: dict) -> dict[str, Any]:
    code = _required_text(input_data, "code")
    timeout = _bounded_int(input_data.get("timeout"), default=10, minimum=1, maximum=30)
    sandbox_result = await execute_python(code, timeout=timeout)
    output = sandbox_result.stdout.strip() or sandbox_result.stderr.strip() or sandbox_result.error
    return {
        "input_summary": f"code_chars={len(code)}; timeout={timeout}",
        "output_summary": output[:2000],
        "error": "" if sandbox_result.success else (sandbox_result.error or sandbox_result.stderr),
        "raw_output": {
            "stdout": sandbox_result.stdout,
            "stderr": sandbox_result.stderr,
            "elapsed_seconds": sandbox_result.elapsed_seconds,
        },
    }


def _required_text(input_data: dict[str, Any], key: str) -> str:
    value = input_data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _summarize_input(input_data: dict[str, Any]) -> str:
    items = []
    for key, value in input_data.items():
        text = str(value)
        items.append(f"{key}={text[:120]}")
    return "; ".join(items)[:1000]


def _result(
    success: bool,
    input_summary: str,
    output_summary: str,
    elapsed_seconds: float,
    error: str = "",
    raw_output: Any = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "input_summary": input_summary[:1000],
        "output_summary": output_summary[:4000],
        "elapsed_seconds": round(elapsed_seconds, 3),
        "error": error[:2000],
        "raw_output": raw_output,
    }
