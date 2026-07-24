"""Runtime readiness checks for research providers and local dependencies."""

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Any

from fastapi import HTTPException

from backend.app.core.db import get_connection
from backend.app.core.runtime_config import sandbox_tool_disabled


_PLACEHOLDER_MARKERS = (
    "your-",
    "your_",
    "replace",
    "changeme",
    "example",
    "sk-your",
    "tvly-your",
)


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
        os.getenv("PLANNER_MODEL", "deepseek-chat"),
        os.getenv("RESEARCHER_MODEL", "deepseek-chat"),
        os.getenv("REPORTER_MODEL", "deepseek-chat"),
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


async def get_readiness() -> dict[str, Any]:
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
    result["ready"] = bool(
        result["model"]["ready"]
        and result["search"]["ready"]
        and result["database"]["ready"]
    )
    return result


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
