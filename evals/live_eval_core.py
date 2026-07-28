"""Pure models and validation for the cost-controlled Live Eval."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLANNED_RUN_LIMIT = 10
ATTEMPT_HARD_LIMIT = 12
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SCHEME_LINK_PATTERN = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s<>\])\"']+")


@dataclass(frozen=True)
class LiveCase:
    id: str
    category: str
    name: str
    topic: str
    budget_profile: str = "fast"
    max_steps: int = 3
    recency_days: int | None = None
    prefer_knowledge_base: bool = False
    repetitions: int = 1


@dataclass
class EvaluationResult:
    case_id: str
    category: str
    attempt: int
    status: str
    passed: bool
    task_id: str = ""
    completed_steps: int = 0
    unique_sources: int = 0
    report_citations: int = 0
    valid_citations: int = 0
    citation_validity: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_rmb: float = 0.0
    search_credits: int = 0
    elapsed_seconds: float = 0.0
    recorded_sources_available: bool = False
    report_structure_valid: bool = False
    checks: dict[str, bool] = field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""


class LiveEvalError(RuntimeError):
    pass


class AttemptBudget:
    """Process-local hard stop for paid research attempts."""

    def __init__(self, limit: int = ATTEMPT_HARD_LIMIT) -> None:
        self.limit = min(limit, ATTEMPT_HARD_LIMIT)
        self.used = 0

    def consume(self) -> int:
        if self.used >= self.limit:
            raise LiveEvalError(
                f"Live Eval attempt hard limit reached: {self.used}/{self.limit}"
            )
        self.used += 1
        return self.used


def load_cases(path: Path) -> list[LiveCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = [LiveCase(**item) for item in data.get("cases", [])]
    categories = {case.category for case in cases}
    required = {"market", "competitive", "technical", "recent", "knowledge_base"}
    if categories != required:
        raise LiveEvalError(f"案例分类必须精确覆盖 {sorted(required)}")
    return cases


def build_formal_schedule(cases: list[LiveCase]) -> list[LiveCase]:
    schedule = [case for case in cases for _ in range(case.repetitions)]
    if len(schedule) != PLANNED_RUN_LIMIT:
        raise LiveEvalError(
            f"正式评估必须精确配置 {PLANNED_RUN_LIMIT} 次，当前为 {len(schedule)} 次"
        )
    return schedule


def ensure_live_enabled(live_flag: bool) -> None:
    if live_flag and os.getenv("RUN_LIVE_E2E") != "1":
        raise LiveEvalError("付费评估被阻止：必须显式设置 RUN_LIVE_E2E=1")


def extract_report_citations(markdown: str) -> set[str]:
    candidates = set(MARKDOWN_LINK_PATTERN.findall(markdown))
    candidates.update(SCHEME_LINK_PATTERN.findall(markdown))
    return {_normalize_source(item) for item in candidates}


def collect_recorded_sources(
    task: dict[str, Any],
    report: dict[str, Any],
    agent_runs: list[dict[str, Any]],
    task_id: str,
    db_path: Path | None,
) -> set[str]:
    sources: set[str] = set()
    for payload in (task, report, *agent_runs):
        sources.update(_sources_from_payload(payload))
    if db_path and db_path.exists():
        sources.update(_sources_from_sqlite(db_path, task_id))
    return {_normalize_source(source) for source in sources if _valid_source_scheme(source)}


def evaluate_payload(
    *,
    case: LiveCase,
    attempt: int,
    task: dict[str, Any],
    report: dict[str, Any],
    agent_runs: list[dict[str, Any]],
    recorded_sources: set[str],
    elapsed_seconds: float,
) -> EvaluationResult:
    markdown = str(report.get("content_markdown") or report.get("report_markdown") or "")
    citations = extract_report_citations(markdown)
    valid_citations = citations & recorded_sources
    prompt_tokens = sum(_as_int(run.get("prompt_tokens")) for run in agent_runs)
    completion_tokens = sum(_as_int(run.get("completion_tokens")) for run in agent_runs)
    total_tokens = _first_int(
        report.get("tokens_used"),
        _nested(task, "usage", "total_tokens"),
        task.get("tokens_used"),
        prompt_tokens + completion_tokens,
    )
    completed_steps = _first_int(
        task.get("current_step"),
        task.get("completed_steps"),
        task.get("total_steps") if task.get("status") == "completed" else 0,
    )
    cost_rmb = _first_float(
        report.get("cost_rmb"),
        _nested(task, "usage", "estimated_cost_rmb"),
        task.get("cost_rmb"),
    )
    search_credits = _first_int(
        _nested(task, "usage", "search_credits"),
        task.get("search_credits"),
        report.get("search_credits"),
        sum(_credits_from_run(run) for run in agent_runs),
    )
    structure_valid = _report_structure_valid(markdown)
    checks = {
        "completed": task.get("status") == "completed",
        "minimum_steps": completed_steps >= 2,
        "minimum_unique_sources": len(recorded_sources) >= 3,
        "recorded_sources_available": bool(recorded_sources),
        "citations_present": bool(citations),
        "citation_scheme_valid": all(_valid_source_scheme(url) for url in citations),
        "citations_recorded": bool(citations) and citations <= recorded_sources,
        "report_structure": structure_valid,
    }
    return EvaluationResult(
        case_id=case.id,
        category=case.category,
        attempt=attempt,
        task_id=str(task.get("task_id") or ""),
        status=str(task.get("status") or "unknown"),
        passed=all(checks.values()),
        completed_steps=completed_steps,
        unique_sources=len(recorded_sources),
        report_citations=len(citations),
        valid_citations=len(valid_citations),
        citation_validity=round(len(valid_citations) / len(citations), 4) if citations else 0.0,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_rmb=cost_rmb,
        search_credits=search_credits,
        elapsed_seconds=round(elapsed_seconds, 3),
        recorded_sources_available=bool(recorded_sources),
        report_structure_valid=structure_valid,
        checks=checks,
        error_code=str(task.get("error_code") or ""),
        error_message=str(task.get("error_message") or ""),
    )


def build_redacted_summary(results: list[EvaluationResult], started_at: str) -> dict[str, Any]:
    completed = sum(result.status == "completed" for result in results)
    passed = sum(result.passed for result in results)
    citations = sum(result.report_citations for result in results)
    valid_citations = sum(result.valid_citations for result in results)
    return {
        "schema_version": "1.0",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "planned_runs": len(results),
        "attempts_used": max((result.attempt for result in results), default=0),
        "completed_runs": completed,
        "passed_runs": passed,
        "completion_rate": round(completed / len(results), 4) if results else 0.0,
        "citation_validity": round(valid_citations / citations, 4) if citations else 0.0,
        "total_tokens": sum(result.total_tokens for result in results),
        "total_cost_rmb": round(sum(result.cost_rmb for result in results), 4),
        "total_search_credits": sum(result.search_credits for result in results),
        "cases": [
            {
                "category": result.category,
                "status": result.status,
                "passed": result.passed,
                "completed_steps": result.completed_steps,
                "unique_sources": result.unique_sources,
                "citation_validity": result.citation_validity,
                "total_tokens": result.total_tokens,
                "cost_rmb": result.cost_rmb,
                "search_credits": result.search_credits,
                "elapsed_seconds": result.elapsed_seconds,
                "error_code": result.error_code,
            }
            for result in results
        ],
    }


def _sources_from_payload(payload: Any) -> set[str]:
    sources: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"url", "uri", "source_url"} and isinstance(value, str):
                sources.add(value)
            elif key in {"sources", "references", "recorded_sources", "source_urls"}:
                sources.update(_sources_from_payload(value))
            elif key == "tool_calls_json" and isinstance(value, str):
                try:
                    sources.update(_sources_from_payload(json.loads(value)))
                except json.JSONDecodeError:
                    pass
            elif isinstance(value, (dict, list)):
                sources.update(_sources_from_payload(value))
    elif isinstance(payload, list):
        for value in payload:
            sources.update(_sources_from_payload(value))
    elif isinstance(payload, str) and _valid_source_scheme(payload):
        sources.add(payload)
    return sources


def _sources_from_sqlite(db_path: Path, task_id: str) -> set[str]:
    sources: set[str] = set()
    try:
        connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        rows = connection.execute(
            "SELECT sources_json FROM research_steps WHERE task_id = ? AND status = 'completed'",
            (task_id,),
        ).fetchall()
        connection.close()
    except sqlite3.Error:
        return sources
    for (raw_sources,) in rows:
        try:
            sources.update(_sources_from_payload(json.loads(raw_sources or "[]")))
        except json.JSONDecodeError:
            continue
    return sources


def _credits_from_run(run: dict[str, Any]) -> int:
    values = [run.get("search_credits")]
    raw = run.get("tool_calls_json")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []
    if isinstance(raw, list):
        values.extend(
            item.get("credits", item.get("search_credits", 0))
            for item in raw
            if isinstance(item, dict)
        )
    return sum(_as_int(value) for value in values)


def _report_structure_valid(markdown: str) -> bool:
    if len(markdown.strip()) < 200 or not re.search(r"(?m)^#\s+\S+", markdown):
        return False
    headings = " ".join(re.findall(r"(?m)^#{2,3}\s+(.+)$", markdown)).lower()
    has_analysis = any(term in headings for term in ("分析", "发现", "overview", "analysis"))
    has_conclusion = any(term in headings for term in ("结论", "总结", "conclusion", "summary"))
    has_sources = any(term in headings for term in ("来源", "引用", "references", "citations"))
    return has_analysis and has_conclusion and has_sources


def _valid_source_scheme(value: str) -> bool:
    return value.strip().startswith(("http://", "https://", "kb://"))


def _normalize_source(value: str) -> str:
    return value.strip().rstrip(".,;:，。；：")


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _first_int(*values: Any) -> int:
    for value in values:
        parsed = _as_int(value)
        if parsed:
            return parsed
    return 0


def _first_float(*values: Any) -> float:
    for value in values:
        try:
            parsed = float(value or 0.0)
        except (TypeError, ValueError):
            continue
        if parsed:
            return parsed
    return 0.0
