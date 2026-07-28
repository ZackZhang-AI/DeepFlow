"""Runtime readiness checks for research providers and local dependencies."""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from backend.app.core.db import get_connection
from backend.app.core.runtime_config import sandbox_tool_disabled
from backend.app.core.errors import classify_failure
from cli.agents.base import LLMProvider
from cli.config import Config


_PLACEHOLDER_MARKERS = (
    "your-",
    "your_",
    "replace",
    "changeme",
    "example",
    "sk-your",
    "tvly-your",
)
_PROBE_TTL_SECONDS = 600
_probe_cache: dict[str, Any] = {}


def _configured(name: str) -> bool:
    value = os.getenv(name, "").strip()
    lowered = value.lower()
    return bool(value) and not any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _provider_status(configured: bool, ready_reason: str, missing_reason: str) -> dict[str, Any]:
    return {
        "configured": configured,
        "ready": configured,
        "reason": ready_reason if configured else missing_reason,
    }


def _required_model_keys() -> set[str]:
    model_names = (
        os.getenv("PLANNER_MODEL", Config.PLANNER_MODEL),
        os.getenv("RESEARCHER_MODEL", Config.RESEARCHER_MODEL),
        os.getenv("REPORTER_MODEL", Config.REPORTER_MODEL),
    )
    return {
        "DASHSCOPE_API_KEY" if model.lower().startswith("qwen") else "DEEPSEEK_API_KEY"
        for model in model_names
    }


def _missing_model_keys() -> list[str]:
    return sorted(key for key in _required_model_keys() if not _configured(key))


async def _docker_status() -> dict[str, Any]:
    enabled = not sandbox_tool_disabled()
    if not enabled:
        return {
            "configured": False,
            "ready": False,
            "reason": "Python sandbox is disabled by DISABLE_SANDBOX_TOOL.",
        }
    if not shutil.which("docker"):
        return {
            "configured": True,
            "ready": False,
            "reason": "Docker executable was not found.",
        }
    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "info",
            "--format",
            "{{.ServerVersion}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=3)
    except (FileNotFoundError, asyncio.TimeoutError, OSError) as exc:
        return {"configured": True, "ready": False, "reason": f"Docker health check failed: {exc}"}
    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        return {
            "configured": True,
            "ready": False,
            "reason": detail[:300] or "Docker daemon is unavailable.",
        }
    version = stdout.decode("utf-8", errors="replace").strip()
    return {
        "configured": True,
        "ready": True,
        "reason": f"Docker daemon is available{f' ({version})' if version else ''}.",
    }


def _database_status() -> dict[str, Any]:
    try:
        connection = get_connection()
        connection.execute("SELECT 1").fetchone()
        connection.close()
    except Exception as exc:
        return {"configured": True, "ready": False, "reason": f"Database check failed: {exc}"}
    return {"configured": True, "ready": True, "reason": "SQLite database is available."}


async def get_readiness(probe: bool = False) -> dict[str, Any]:
    missing_model_keys = _missing_model_keys()
    model_configured = not missing_model_keys
    search_configured = _configured("TAVILY_API_KEY") or _configured("SERPAPI_API_KEY")
    embedding_configured = _configured("DASHSCOPE_API_KEY")
    result = {
        "model": _provider_status(
            model_configured,
            "All model providers required by the configured agents are available.",
            f"Configure required model keys: {', '.join(missing_model_keys)}.",
        ),
        "search": _provider_status(
            search_configured,
            "At least one search provider is configured.",
            "Configure TAVILY_API_KEY or SERPAPI_API_KEY.",
        ),
        "embedding": _provider_status(
            embedding_configured,
            "DashScope embedding provider is configured.",
            "DASHSCOPE_API_KEY is not configured; public-search research remains available.",
        ),
        "docker": await _docker_status(),
        "database": _database_status(),
    }
    result["model"].update(
        {
            "models": sorted(_required_model_names()),
            "probed": False,
            "checked_at": None,
            "error_code": "",
        }
    )
    if probe and model_configured:
        result["model"].update(await _probe_model_provider())
    result["ready"] = bool(
        result["model"]["ready"]
        and result["search"]["ready"]
        and result["database"]["ready"]
    )
    return result


def _required_model_names() -> set[str]:
    return {
        os.getenv("PLANNER_MODEL", Config.PLANNER_MODEL),
        os.getenv("RESEARCHER_MODEL", Config.RESEARCHER_MODEL),
        os.getenv("REPORTER_MODEL", Config.REPORTER_MODEL),
    }


async def _probe_model_provider() -> dict[str, Any]:
    now = time.monotonic()
    if _probe_cache and now - float(_probe_cache.get("cached_at") or 0) < _PROBE_TTL_SECONDS:
        return dict(_probe_cache["result"])

    model = os.getenv("PLANNER_MODEL", Config.PLANNER_MODEL)
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        await LLMProvider.generate_text(
            model=model,
            system_prompt="Return only OK.",
            user_message="Provider readiness check.",
            temperature=0,
            max_tokens=8,
        )
        probe_result = {
            "ready": True,
            "probed": True,
            "checked_at": checked_at,
            "error_code": "",
            "reason": f"Model provider probe succeeded with {model}.",
        }
    except Exception as exc:
        failure = classify_failure(exc)
        probe_result = {
            "ready": False,
            "probed": True,
            "checked_at": checked_at,
            "error_code": failure.code,
            "reason": failure.message[:300],
        }
    _probe_cache.clear()
    _probe_cache.update({"cached_at": now, "result": probe_result})
    return probe_result


def reset_readiness_probe_cache() -> None:
    _probe_cache.clear()


def require_research_providers() -> None:
    """Reject research creation when model or search providers are missing."""
    missing: list[str] = []
    missing_model_keys = _missing_model_keys()
    if missing_model_keys:
        missing.append(f"model provider ({', '.join(missing_model_keys)})")
    if not (_configured("TAVILY_API_KEY") or _configured("SERPAPI_API_KEY")):
        missing.append("search provider (TAVILY_API_KEY or SERPAPI_API_KEY)")
    if missing:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PROVIDER_NOT_READY",
                "message": "Research providers are not configured.",
                "missing": missing,
            },
        )
