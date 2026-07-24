"""Stable error codes and retry decisions for background work."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Failure:
    code: str
    message: str
    retryable: bool


def classify_failure(exc: BaseException) -> Failure:
    message = str(exc).strip() or exc.__class__.__name__
    text = message.lower()

    if any(token in text for token in ("401", "403", "unauthorized", "forbidden", "api key")):
        return Failure("provider_auth", message, False)
    if any(token in text for token in ("budget", "token budget", "quota exceeded")):
        return Failure("budget_exceeded", message, False)
    if any(token in text for token in ("not configured", "missing", "未配置", "配置缺失")):
        return Failure("provider_not_configured", message, False)
    if "429" in text or "rate limit" in text or "too many requests" in text:
        return Failure("provider_rate_limited", message, True)
    if any(token in text for token in ("timeout", "timed out", "connection", "502", "503", "504", "5xx")):
        return Failure("provider_unavailable", message, True)
    if any(token in text for token in ("no search results", "empty search", "无搜索结果")):
        return Failure("search_empty", message, True)
    return Failure("internal_error", message, False)
