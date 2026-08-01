import json

import pytest
from fastapi import HTTPException

from backend.app.api.routes.templates import _build_template_plan
from backend.app.core.readiness import require_research_providers
from cli.models import ResearchPlan, StepType
from cli.tools import sandbox


def test_legacy_template_steps_produce_valid_research_plan():
    payload = _build_template_plan(
        topic="AI research platform market",
        locale="zh-CN",
        template_id="tmpl_test",
        report_style="market",
        plan_structure=[
            {"name": "市场概览", "query": "市场规模", "search_required": True},
            {"title": "整理结论", "description": "汇总发现", "type": "analysis"},
        ],
    )

    plan = ResearchPlan.model_validate_json(json.dumps(payload, ensure_ascii=False))

    assert plan.title == "AI research platform market"
    assert plan.locale == "zh-CN"
    assert plan.steps[0].title == "市场概览"
    assert plan.steps[0].step_type == StepType.RESEARCH
    assert plan.steps[1].step_type == StepType.PROCESSING
    assert plan.steps[1].need_search is False


@pytest.mark.asyncio
async def test_public_sandbox_does_not_fallback_when_docker_is_missing(monkeypatch):
    local_called = False

    async def fake_subprocess(*args, **kwargs):
        nonlocal local_called
        local_called = True
        raise AssertionError("local subprocess fallback must not run")

    async def missing_docker(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(sandbox, "_run_subprocess", fake_subprocess)
    monkeypatch.setattr(sandbox.asyncio, "create_subprocess_exec", missing_docker)

    result = await sandbox.execute_python("print(1)")

    assert result.success is False
    assert "local fallback is disabled" in result.error
    assert local_called is False


def test_research_readiness_requires_keys_for_configured_models(monkeypatch):
    monkeypatch.setenv("PLANNER_MODEL", "deepseek-chat")
    monkeypatch.setenv("RESEARCHER_MODEL", "deepseek-chat")
    monkeypatch.setenv("REPORTER_MODEL", "qwen-max")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-test-value")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-real-test-value")

    with pytest.raises(HTTPException) as caught:
        require_research_providers()

    assert caught.value.status_code == 503
    assert "DASHSCOPE_API_KEY" in str(caught.value.detail)
