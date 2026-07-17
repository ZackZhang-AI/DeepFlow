"""Runtime configuration helpers for deploy-safe demo settings."""

from __future__ import annotations

import os
from pathlib import Path


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None else default
    except ValueError:
        value = default
    if minimum is not None:
        return max(value, minimum)
    return value


def database_path(default_path: Path) -> Path:
    configured = os.getenv("DEEPFLOW_DB_PATH", "").strip()
    return Path(configured) if configured else default_path


def public_registration_allowed() -> bool:
    return env_bool("ALLOW_PUBLIC_REGISTRATION", True)


def demo_credentials() -> tuple[str, str] | None:
    username = os.getenv("DEMO_USERNAME", "").strip()
    password = os.getenv("DEMO_PASSWORD", "")
    if not username or not password:
        return None
    return username, password


def sandbox_tool_disabled() -> bool:
    return env_bool("DISABLE_SANDBOX_TOOL", False)


def rate_limit_window_seconds() -> int:
    return env_int("RATE_LIMIT_WINDOW_SECONDS", 3600, minimum=1)


def research_task_rate_limit() -> int:
    return env_int("RESEARCH_TASK_RATE_LIMIT_PER_HOUR", 20, minimum=0)


def tool_test_rate_limit() -> int:
    return env_int("TOOL_TEST_RATE_LIMIT_PER_HOUR", 30, minimum=0)


def knowledge_write_rate_limit() -> int:
    return env_int("KNOWLEDGE_WRITE_RATE_LIMIT_PER_HOUR", 20, minimum=0)


def artifact_rate_limit() -> int:
    return env_int("ARTIFACT_RATE_LIMIT_PER_HOUR", 20, minimum=0)


def knowledge_upload_max_bytes() -> int:
    return env_int("KNOWLEDGE_UPLOAD_MAX_BYTES", 5 * 1024 * 1024, minimum=1)
