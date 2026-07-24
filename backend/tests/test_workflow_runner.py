import asyncio
import json
from datetime import datetime

from backend.app.api.routes import workflows
from backend.app.core import db
from backend.app.services import workflow_runner
from cli.models import (
    ResearchFinding,
    ResearchPlan,
    ResearchStep,
    SourceReference,
    StepType,
)


def _plan() -> ResearchPlan:
    return ResearchPlan(
        title="Real agent workflow",
        locale="zh-CN",
        steps=[
            ResearchStep(
                title="Research the market",
                description="Collect traceable evidence.",
                need_search=True,
                step_type=StepType.RESEARCH,
            )
        ],
    )


def _finding() -> ResearchFinding:
    return ResearchFinding(
        step_id="step_1",
        step_title="Research the market",
        problem_statement="Collect traceable evidence.",
        findings_markdown="Evidence from the source.",
        conclusion="The evidence supports the conclusion.",
        references=[
            SourceReference(
                title="Source",
                url="https://example.com/source",
            )
        ],
    )


def test_workflow_calls_real_agent_functions(monkeypatch):
    calls: list[str] = []
    traces: list[dict] = []

    async def fake_plan(**kwargs):
        calls.append("planner")
        return _plan(), 10, 5

    async def fake_research(**kwargs):
        calls.append("researcher")
        return _finding(), 20, 10

    async def fake_report(**kwargs):
        calls.append("reporter")
        assert kwargs["findings"][0].references[0].url == "https://example.com/source"
        return "# Verified report", 30, 15

    monkeypatch.setattr(workflow_runner, "generate_plan", fake_plan)
    monkeypatch.setattr(workflow_runner, "research_step", fake_research)
    monkeypatch.setattr(workflow_runner, "generate_report", fake_report)
    monkeypatch.setattr(workflow_runner, "_save_node_trace", lambda **kwargs: traces.append(kwargs))

    result = asyncio.run(
        workflow_runner.execute_workflow(
            nodes=[
                {"id": "plan", "type": "Planner"},
                {"id": "research", "type": "Researcher"},
                {"id": "report", "type": "Reporter"},
            ],
            workflow_input={"topic": "DeepFlow"},
            user={"user_id": "user_test"},
            workflow_id="wf_test",
            run_id="run_test",
            budget={"max_steps": 3, "max_tokens": 100},
        )
    )

    assert result["status"] == "completed"
    assert calls == ["planner", "researcher", "reporter"]
    assert result["token_usage"] == 90
    assert result["outputs"]["report"]["markdown"] == "# Verified report"
    assert [trace["node_type"] for trace in traces] == ["Planner", "Researcher", "Reporter"]
    assert result["execution_mode"] == "sequential"
    assert result["edges_applied"] is False


def test_human_feedback_pauses_and_resumes_from_next_node(monkeypatch):
    calls: list[str] = []
    traces: list[dict] = []

    async def fake_plan(**kwargs):
        calls.append("planner")
        return _plan(), 1, 1

    async def fake_research(**kwargs):
        calls.append("researcher")
        return _finding(), 1, 1

    monkeypatch.setattr(workflow_runner, "generate_plan", fake_plan)
    monkeypatch.setattr(workflow_runner, "research_step", fake_research)
    monkeypatch.setattr(workflow_runner, "_save_node_trace", lambda **kwargs: traces.append(kwargs))

    nodes = [
        {"id": "plan", "type": "Planner"},
        {
            "id": "approval",
            "type": "Human Feedback",
            "config": {"pause": True, "instruction": "Approve this plan"},
        },
        {"id": "research", "type": "Researcher"},
    ]
    paused = asyncio.run(
        workflow_runner.execute_workflow(
            nodes=nodes,
            workflow_input={"topic": "DeepFlow"},
            user={"user_id": "user_test"},
            workflow_id="wf_test",
            run_id="run_test",
        )
    )

    assert paused["status"] == "waiting_feedback"
    assert paused["next_node_index"] == 2
    assert calls == ["planner"]
    assert traces[-1]["status"] == "waiting_feedback"

    checkpoint = workflow_runner.apply_feedback(paused, {"approved": True})
    resumed = asyncio.run(
        workflow_runner.execute_workflow(
            nodes=nodes,
            workflow_input={"topic": "DeepFlow", "human_feedback": checkpoint["feedback"]},
            user={"user_id": "user_test"},
            workflow_id="wf_test",
            run_id="run_test",
            checkpoint=checkpoint,
            start_index=checkpoint["next_node_index"],
        )
    )

    assert resumed["status"] == "completed"
    assert calls == ["planner", "researcher"]
    assert resumed["outputs"]["approval"]["feedback"] == {"approved": True}
    assert resumed["feedback"][0]["node_id"] == "approval"


def test_node_retry_and_token_budget(monkeypatch):
    attempts = 0
    traces: list[dict] = []

    async def flaky_plan(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary provider timeout")
        return _plan(), 8, 4

    monkeypatch.setattr(workflow_runner, "generate_plan", flaky_plan)
    monkeypatch.setattr(workflow_runner, "_save_node_trace", lambda **kwargs: traces.append(kwargs))

    result = asyncio.run(
        workflow_runner.execute_workflow(
            nodes=[{"id": "plan", "type": "Planner", "retry": 1}],
            workflow_input={"topic": "DeepFlow"},
            user={"user_id": "user_test"},
            workflow_id="wf_test",
            run_id="run_test",
            budget={"max_tokens": 10},
        )
    )

    assert attempts == 2
    assert [trace["status"] for trace in traces] == ["failed", "completed"]
    assert result["status"] == "failed"
    assert "token budget exceeded" in result["error"].lower()


def test_resume_route_persists_feedback_and_completion(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "workflow_resume.db"
    db.init_db()
    now = datetime.now().isoformat()
    paused = {
        "status": "waiting_feedback",
        "outputs": {
            "approval": {
                "pending": True,
                "instruction": "Approve this output",
            }
        },
        "trace": [],
        "next_node_index": 1,
        "token_usage": 0,
        "waiting_node_id": "approval",
        "feedback": [],
        "execution_mode": "sequential",
        "edges_applied": False,
        "error": "",
    }
    conn = db.get_connection()
    conn.execute(
        """INSERT INTO workflows
           (workflow_id, user_id, name, description, nodes_json, edges_json, budget_json, created_at, updated_at)
           VALUES (?, ?, ?, '', ?, '[]', '{}', ?, ?)""",
        (
            "wf_resume",
            "user_test",
            "Resume workflow",
            json.dumps(
                [
                    {
                        "id": "approval",
                        "type": "Human Feedback",
                        "config": {"pause": True},
                    },
                    {
                        "id": "artifact",
                        "type": "Artifact",
                        "config": {"content": "approved"},
                    },
                ]
            ),
            now,
            now,
        ),
    )
    conn.execute(
        """INSERT INTO workflow_runs
           (run_id, workflow_id, user_id, status, input_json, outputs_json, error, created_at, updated_at)
           VALUES (?, ?, ?, 'waiting_feedback', '{}', ?, '', ?, ?)""",
        ("run_resume", "wf_resume", "user_test", json.dumps(paused), now, now),
    )
    conn.commit()
    conn.close()

    response = asyncio.run(
        workflows.resume_workflow_run(
            "run_resume",
            workflows.ResumeWorkflowRequest(feedback={"approved": True}),
            {"user_id": "user_test"},
        )
    )

    assert response["status"] == "completed"
    checkpoint = response["outputs"]
    assert checkpoint["outputs"]["approval"]["feedback"] == {"approved": True}
    assert checkpoint["outputs"]["artifact"]["content"] == "approved"
    stored = db.get_connection().execute(
        "SELECT status FROM workflow_runs WHERE run_id = ?",
        ("run_resume",),
    ).fetchone()
    assert stored["status"] == "completed"
