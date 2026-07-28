"""Stable error codes and retry decisions for background work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException


@dataclass(frozen=True)
class Failure:
    code: str
    message: str
    retryable: bool


class APIError(HTTPException):
    """HTTP error with a stable machine-readable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: Any = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.details = details


def http_error_payload(exc: HTTPException) -> dict[str, Any]:
    detail = exc.detail
    message = detail if isinstance(detail, str) else "Request failed"
    code = getattr(exc, "code", None) or _status_code(exc.status_code)
    return {
        "error_code": code,
        "message": message,
        "detail": detail,
        "details": getattr(exc, "details", None),
    }


def _status_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "authentication_required",
        403: "permission_denied",
        404: "resource_not_found",
        409: "resource_conflict",
        410: "resource_expired",
        413: "payload_too_large",
        422: "validation_error",
        429: "rate_limited",
        503: "service_unavailable",
    }.get(status_code, "request_failed")


def classify_failure(exc: BaseException) -> Failure:
    message = str(exc).strip() or exc.__class__.__name__
    text = message.lower()

    if any(
        token in text
        for token in ("402", "insufficient balance", "payment required", "余额不足")
    ):
        return Failure("provider_balance_exhausted", message, False)
    if any(
        token in text
        for token in ("search credits", "tavily credits", "credit balance exhausted")
    ):
        return Failure("search_credits_exhausted", message, False)
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
