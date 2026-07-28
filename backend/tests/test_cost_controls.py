import asyncio
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.core import db
from backend.app.core.errors import classify_failure
from backend.app.core.readiness import get_readiness, reset_readiness_probe_cache
from backend.app.core.runtime_config import sandbox_tool_disabled
from backend.app.main import app
from backend.app.repositories.research import create_task, get_usage_summary, update_task
from cli.agents.base import _apply_deepseek_options
from cli.agents.reporter import generate_report
from cli.agents.researcher import research_step
from cli.budget import get_budget
from cli.models import ResearchFinding, ResearchPlan
from cli.pricing import PRICING_VERSION, estimate_cost_rmb
from cli.tools.web_search import _tavily_search


def _use_temp_db(tmp_path, monkeypatch):
    db.DB_PATH = tmp_path / "cost_controls.db"
    monkeypatch.setenv("DEEPFLOW_DB_PATH", str(db.DB_PATH))
    db.init_db()


def test_budget_profiles_are_fixed():
    assert get_budget("fast").model_dump() == {
        "profile": "fast",
        "max_steps": 3,
        "max_search_calls_per_step": 1,
        "max_crawl_pages_per_step": 1,
        "max_tokens": 20_000,
        "search_depth": "basic",
    }
    assert get_budget("standard").max_tokens == 40_000
    assert get_budget("deep").search_depth == "advanced"
    assert get_budget("unknown").profile == "fast"


def test_sandbox_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DISABLE_SANDBOX_TOOL", raising=False)
    assert sandbox_tool_disabled() is True


def test_v4_requests_disable_thinking_by_default(monkeypatch):
    monkeypatch.setattr("cli.config.Config.DEEPSEEK_THINKING_ENABLED", False)
    request = {}
    _apply_deepseek_options(request, "deepseek-v4-flash")
    assert request["extra_body"] == {"thinking": {"type": "disabled"}}

    legacy_request = {}
    _apply_deepseek_options(legacy_request, "qwen-max")
    assert "extra_body" not in legacy_request


def test_versioned_model_pricing_and_balance_error(monkeypatch):
    monkeypatch.setenv("USD_TO_CNY_RATE", "7.2")
    flash = estimate_cost_rmb("deepseek-v4-flash", 1_000_000, 1_000_000)
    pro = estimate_cost_rmb("deepseek-v4-pro", 1_000_000, 1_000_000)
    assert flash == 3.024
    assert pro == 9.396
    assert PRICING_VERSION

    failure = classify_failure(RuntimeError("HTTP 402 Payment Required: Insufficient Balance"))
    assert failure.code == "provider_balance_exhausted"
    assert failure.retryable is False


def test_task_budget_and_usage_summary_are_persisted(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    task = create_task(
        "task_budget_fast",
        "budget",
        user_id=db.LOCAL_DEFAULT_USER_ID,
        budget_profile="fast",
        max_steps=3,
        max_tokens_budget=20_000,
        pricing_version=PRICING_VERSION,
    )
    assert task["budget_profile"] == "fast"
    assert task["max_tokens_budget"] == 20_000

    update_task(
        task["task_id"],
        status="completed",
        prompt_tokens=1200,
        completion_tokens=800,
        tokens_used=2000,
        cost_rmb=0.02,
        search_credits=3,
    )
    summary = get_usage_summary(db.LOCAL_DEFAULT_USER_ID)
    assert summary["total_tasks"] == 1
    assert summary["completed_tasks"] == 1
    assert summary["total_tokens"] == 2000
    assert summary["total_search_credits"] == 3


def test_tavily_usage_credits_are_returned(monkeypatch):
    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def search(self, **kwargs):
            assert kwargs["include_usage"] is True
            assert kwargs["search_depth"] == "advanced"
            return {
                "results": [
                    {
                        "title": "Source",
                        "url": "https://example.com",
                        "content": "Evidence",
                    }
                ],
                "usage": {"credits": 2},
            }

    monkeypatch.setitem(sys.modules, "tavily", SimpleNamespace(TavilyClient=FakeClient))
    monkeypatch.setattr("cli.config.Config.TAVILY_API_KEY", "test-key")
    batch = asyncio.run(_tavily_search("query", search_depth="advanced"))
    assert batch.credits == 2
    assert batch.provider == "tavily"
    assert len(batch.results) == 1


def test_readiness_probe_is_cached(monkeypatch, tmp_path):
    _use_temp_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("PLANNER_MODEL", "deepseek-v4-flash")
    calls = 0

    async def fake_generate_text(**_kwargs):
        nonlocal calls
        calls += 1
        return "OK", 1, 1

    monkeypatch.setattr(
        "backend.app.core.readiness.LLMProvider.generate_text",
        fake_generate_text,
    )
    reset_readiness_probe_cache()
    first = asyncio.run(get_readiness(probe=True))
    second = asyncio.run(get_readiness(probe=True))
    assert first["model"]["probed"] is True
    assert second["model"]["ready"] is True
    assert calls == 1


def test_fast_reporter_honors_output_budget(monkeypatch):
    captured = {}

    async def fake_generate_text(**kwargs):
        captured.update(kwargs)
        return "# 报告\n\n" + ("有效内容" * 100), 100, 200

    monkeypatch.setattr(
        "cli.agents.reporter.LLMProvider.generate_text",
        fake_generate_text,
    )
    asyncio.run(
        generate_report(
            ResearchPlan(title="预算研究"),
            [
                ResearchFinding(
                    step_id="step_1",
                    problem_statement="问题",
                    findings_markdown="发现" * 2_000,
                    conclusion="结论" * 500,
                )
            ],
            model_override="deepseek-v4-flash",
            max_output_tokens=1536,
            max_finding_chars_per_step=800,
        )
    )
    assert captured["max_tokens"] == 1536
    assert len(captured["user_message"]) < 3000
    assert "## 结论、## 主要分析、## 来源" in captured["user_message"]


def test_fast_researcher_honors_summary_budget(monkeypatch):
    calls = []

    async def fake_generate_text(**kwargs):
        calls.append(kwargs["max_tokens"])
        if len(calls) == 1:
            return "test query", 10, 5
        return "## Analysis\nEvidence\n\n## Conclusion\nDone", 20, 10

    async def fake_search(*_args, **_kwargs):
        from cli.models import SearchBatch, SearchResult

        return SearchBatch(
            results=[
                SearchResult(
                    title="Source",
                    url="https://example.com",
                    snippet="Evidence",
                )
            ],
            credits=1,
            provider="tavily",
        )

    monkeypatch.setattr(
        "cli.agents.researcher.LLMProvider.generate_text",
        fake_generate_text,
    )
    monkeypatch.setattr("cli.agents.researcher.web_search_multi", fake_search)
    monkeypatch.setattr("cli.agents.researcher.crawl_urls", lambda _urls: asyncio.sleep(0, result=[]))
    from cli.models import ResearchStep, StepType

    asyncio.run(
        research_step(
            ResearchStep(
                title="测试",
                description="测试预算",
                need_search=True,
                step_type=StepType.RESEARCH,
            ),
            1,
            1,
            max_search_calls=1,
            max_crawl_pages=1,
            max_summary_tokens=2048,
        )
    )
    assert calls == [512, 2048]


def test_clarification_response_keeps_budget_contract(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        "backend.app.api.routes.research.enqueue_job",
        lambda *_args, **_kwargs: None,
    )

    with TestClient(app) as client:
        registration = client.post(
            "/api/auth/register",
            json={"username": "budget_clarification", "password": "password123"},
        )
        token = registration.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post(
            "/api/research-tasks",
            headers=headers,
            json={"topic": "AI", "budget_profile": "fast"},
        )
        assert created.status_code == 201, created.text
        task_id = created.json()["task_id"]

        answered = client.post(
            f"/api/research-tasks/{task_id}/clarifications",
            headers=headers,
            json={"answers": {"0": "研究企业 AI Agent 市场"}},
        )

    assert answered.status_code == 200, answered.text
    payload = answered.json()
    assert payload["budget"]["profile"] == "fast"
    assert payload["usage"]["total_tokens"] == 0
