from __future__ import annotations

import json

import pytest

from evals.live_eval import (
    ATTEMPT_HARD_LIMIT,
    AttemptBudget,
    LiveCase,
    LiveEvalError,
    build_formal_schedule,
    build_redacted_summary,
    ensure_live_enabled,
    evaluate_payload,
    extract_report_citations,
    load_cases,
    main,
)


def _case() -> LiveCase:
    return LiveCase(
        id="market",
        category="market",
        name="市场分析",
        topic="测试主题",
    )


def test_default_entry_is_dry_run_and_never_builds_api(monkeypatch, capsys):
    monkeypatch.delenv("RUN_LIVE_E2E", raising=False)
    assert main([]) == 0
    assert "未发送任何 API 请求" in capsys.readouterr().out


def test_live_requires_explicit_environment_switch(monkeypatch):
    monkeypatch.delenv("RUN_LIVE_E2E", raising=False)
    with pytest.raises(LiveEvalError):
        ensure_live_enabled(True)


def test_fixed_cases_and_formal_schedule_have_controlled_size():
    cases = load_cases()
    assert {case.category for case in cases} == {
        "market",
        "competitive",
        "technical",
        "recent",
        "knowledge_base",
    }
    assert len(build_formal_schedule(cases)) == 10


def test_attempt_budget_has_unconditional_hard_limit():
    budget = AttemptBudget(limit=999)
    for expected in range(1, ATTEMPT_HARD_LIMIT + 1):
        assert budget.consume() == expected
    with pytest.raises(LiveEvalError):
        budget.consume()


def test_evaluation_accepts_missing_new_usage_fields_as_zero():
    sources = {
        "https://example.com/a",
        "https://example.com/b",
        "kb://doc_1#chunk_1",
    }
    report = {
        "content_markdown": (
            "# 报告\n\n## 主要分析\n" + "有效内容。" * 80
            + "\n\n## 结论\n结论。\n\n## 来源\n"
            + "\n".join(f"- [来源]({source})" for source in sorted(sources))
        )
    }
    result = evaluate_payload(
        case=_case(),
        attempt=1,
        task={"task_id": "task_1", "status": "completed", "current_step": 2},
        report=report,
        agent_runs=[],
        recorded_sources=sources,
        elapsed_seconds=1.25,
    )
    assert result.passed
    assert result.total_tokens == 0
    assert result.cost_rmb == 0.0
    assert result.search_credits == 0
    assert result.citation_validity == 1.0


def test_unrecorded_or_unsupported_citations_fail_validation():
    markdown = (
        "# 报告\n\n## 主要分析\n" + "内容。" * 100
        + "\n\n## 结论\n结论。\n\n## 引用\n"
        + "[记录](https://example.com/a) [编造](https://invalid.example/x)"
        + " ftp://example.com/file"
    )
    result = evaluate_payload(
        case=_case(),
        attempt=1,
        task={"task_id": "task_2", "status": "completed", "current_step": 3},
        report={"content_markdown": markdown},
        agent_runs=[],
        recorded_sources={
            "https://example.com/a",
            "https://example.com/b",
            "kb://doc_1#chunk_1",
        },
        elapsed_seconds=1,
    )
    assert not result.passed
    assert not result.checks["citations_recorded"]
    assert not result.checks["citation_scheme_valid"]
    assert "ftp://example.com/file" in extract_report_citations(markdown)


def test_redacted_summary_excludes_task_ids_topics_and_source_urls():
    result = evaluate_payload(
        case=_case(),
        attempt=1,
        task={"task_id": "secret-task", "status": "failed", "error_code": "timeout"},
        report={},
        agent_runs=[],
        recorded_sources=set(),
        elapsed_seconds=2,
    )
    summary = build_redacted_summary([result], "2026-01-01T00:00:00+00:00")
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "secret-task" not in serialized
    assert "测试主题" not in serialized
    assert "http" not in serialized
