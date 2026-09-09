from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.api.routes.research import _task_response
from backend.app.core import db
from backend.app.core.events import append_event, list_events
from backend.app.core.job_queue import (
    _claim_next_job,
    enqueue_job,
    recover_interrupted_jobs,
)


def _use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "deepflow-test.db")
    db.init_db()


def test_research_events_replay_after_sequence(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    db.create_task("task_events", "event replay", user_id=db.LOCAL_DEFAULT_USER_ID)

    first = append_event("task_events", "step.started", {"step_index": 1})
    second = append_event("task_events", "step.completed", {"step_index": 1})

    replay = list_events("task_events", after_seq=first)
    assert second > first
    assert [event["sequence"] for event in replay] == [second]
    assert replay[0]["data"]["step_index"] == 1


def test_interrupted_job_is_requeued_and_claimed(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    job_id = enqueue_job(
        "research_plan",
        user_id=db.LOCAL_DEFAULT_USER_ID,
        task_id=None,
        payload={"topic": "durable queue"},
    )
    stale = (datetime.now() - timedelta(minutes=5)).isoformat()
    conn = db.get_connection()
    conn.execute(
        """UPDATE background_jobs SET status = 'running', locked_at = ?, heartbeat_at = ?
           WHERE job_id = ?""",
        (stale, stale, job_id),
    )
    conn.commit()
    conn.close()

    assert recover_interrupted_jobs(stale_seconds=30) == 1
    claimed = _claim_next_job()
    assert claimed is not None
    assert claimed["job_id"] == job_id
    assert claimed["payload"]["topic"] == "durable queue"


def test_pending_text_document_can_be_processed(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    from backend.app.services import knowledge

    class FakeEmbedding:
        def embed_documents(self, texts, batch_size=16):
            return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(knowledge, "get_embedding_service", lambda: FakeEmbedding())
    doc = knowledge.queue_text_document(
        title="Async RAG",
        content="DeepFlow async knowledge indexing " * 80,
        user_id=db.LOCAL_DEFAULT_USER_ID,
    )
    assert doc["status"] == "pending"

    ready = knowledge.process_pending_document(doc["doc_id"], db.LOCAL_DEFAULT_USER_ID)
    assert ready["status"] == "ready"
    assert ready["chunk_count"] > 0
    assert ready["embedding_dimensions"] == 2
    assert ready["embedding_provider"] == "fakeembedding"
    assert ready["index_version"] == "1"


def test_local_embedding_supports_zero_cost_private_knowledge():
    from backend.app.services.embedding import LocalHashEmbeddingService, _usable_api_key

    service = LocalHashEmbeddingService()
    first = service.embed_query("DeepFlow 私域知识库")
    second = service.embed_query("DeepFlow 私域知识库")

    assert first == second
    assert len(first) == service.dimensions
    assert any(value != 0 for value in first)
    assert not _usable_api_key("your-dashscope-api-key")
    assert _usable_api_key("sk-real-value")


def test_knowledge_search_only_uses_selected_documents(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    from backend.app.services import knowledge
    from backend.app.services.embedding import LocalHashEmbeddingService

    monkeypatch.setattr(knowledge, "get_embedding_service", lambda: LocalHashEmbeddingService())
    first = knowledge.queue_text_document(
        title="产品定位",
        content="DeepFlow 是一个可追溯的 AI 深度研究工作台。" * 40,
        user_id=db.LOCAL_DEFAULT_USER_ID,
    )
    second = knowledge.queue_text_document(
        title="风险边界",
        content="DeepFlow 的风险包括第三方 Provider 波动和预算限制。" * 40,
        user_id=db.LOCAL_DEFAULT_USER_ID,
    )
    knowledge.process_pending_document(first["doc_id"], db.LOCAL_DEFAULT_USER_ID)
    knowledge.process_pending_document(second["doc_id"], db.LOCAL_DEFAULT_USER_ID)

    hits = knowledge.search_knowledge_chunks(
        "DeepFlow 风险 Provider",
        limit=5,
        score_threshold=0,
        user_id=db.LOCAL_DEFAULT_USER_ID,
        document_ids=[second["doc_id"]],
    )

    assert hits
    assert {hit["doc_id"] for hit in hits} == {second["doc_id"]}


def test_knowledge_search_requires_reindex_after_embedding_change(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    from backend.app.services import knowledge
    from backend.app.services.embedding import LocalHashEmbeddingService

    monkeypatch.setattr(knowledge, "get_embedding_service", lambda: LocalHashEmbeddingService())
    document = knowledge.queue_text_document(
        title="旧索引",
        content="DeepFlow 私域知识库索引兼容性。" * 40,
        user_id=db.LOCAL_DEFAULT_USER_ID,
    )
    knowledge.process_pending_document(document["doc_id"], db.LOCAL_DEFAULT_USER_ID)
    db.update_knowledge_document(document["doc_id"], embedding_model="legacy-model")

    with __import__("pytest").raises(knowledge.KnowledgeIndexCompatibilityError) as exc_info:
        knowledge.search_knowledge_chunks(
            "索引兼容性",
            score_threshold=0,
            user_id=db.LOCAL_DEFAULT_USER_ID,
            document_ids=[document["doc_id"]],
        )

    assert exc_info.value.document_ids == [document["doc_id"]]


def test_report_removes_sources_not_recorded_by_researcher():
    from cli.agents.reporter import _remove_unrecorded_links

    report = (
        "[Recorded](https://example.com/source) "
        "[Invented](https://invalid.example/fake) "
        "[Knowledge](kb://doc_1#chunk_1)"
    )
    cleaned = _remove_unrecorded_links(
        report,
        {"https://example.com/source", "kb://doc_1#chunk_1"},
    )
    assert "https://example.com/source" in cleaned
    assert "kb://doc_1#chunk_1" in cleaned
    assert "invalid.example" not in cleaned


def test_research_budget_survives_clarification_checkpoint(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    task = db.create_task(
        "task_budget",
        "budget persistence",
        user_id=db.LOCAL_DEFAULT_USER_ID,
        max_steps=2,
    )
    assert task["max_steps"] == 2


def test_research_task_persists_private_knowledge_selection(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    task = db.create_task(
        "task_private_knowledge",
        "selected knowledge",
        user_id=db.LOCAL_DEFAULT_USER_ID,
        knowledge_enabled=True,
        knowledge_document_ids=["doc_a", "doc_b"],
    )
    response = _task_response(task)

    assert response.knowledge_enabled is True
    assert response.knowledge_document_ids == ["doc_a", "doc_b"]


def test_research_sources_keep_step_provenance(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    from backend.app.api.routes.research import get_research_sources

    task = db.create_task("task_sources", "evidence", user_id=db.LOCAL_DEFAULT_USER_ID)
    step_id = db.save_step(task["task_id"], 1, "市场规模", "核对市场规模")
    db.update_step(
        step_id,
        status="completed",
        findings_markdown="市场数据来自 [权威来源](https://example.com/source)，可用于判断趋势。",
        sources_json=[
            {
                "title": "权威来源",
                "url": "https://example.com/source",
                "source_type": "web",
                "snippet": "关键证据摘要",
                "published_at": "2026-01-01",
                "confidence": 0.8,
            }
        ],
    )

    sources = asyncio.run(
        get_research_sources(task["task_id"], user={"user_id": db.LOCAL_DEFAULT_USER_ID})
    )
    assert sources[0]["title"] == "权威来源"
    assert sources[0]["steps"] == [{"step_index": 1, "step_title": "市场规模"}]
    assert sources[0]["claims"] == ["市场数据来自 权威来源，可用于判断趋势。"]


def test_clarification_questions_progress_without_repeating():
    from backend.app.api.routes.research import _build_clarification_questions

    first = _build_clarification_questions("研究 AI")
    assert 1 <= len(first) <= 2
    second = _build_clarification_questions(
        "研究 AI\n用户补充信息：\n- 面向产品经理决策",
        history=[{"questions": first}],
    )
    assert not set(first) & set(second)
    assert len(second) <= 2


def test_plan_revision_replaces_steps_and_keeps_budget(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    from backend.app.api.routes.research import revise_plan
    from backend.app.models.schemas import RevisePlanRequest
    from cli.models import ResearchPlan, ResearchStep

    task = db.create_task(
        "task_revise_plan",
        "AI 产品研究",
        user_id=db.LOCAL_DEFAULT_USER_ID,
        max_steps=3,
    )
    original = ResearchPlan(
        title="原计划",
        steps=[ResearchStep(title="旧步骤", description="旧内容", need_search=True, step_type="research")],
    )
    db.update_task(task["task_id"], status="awaiting_confirmation", plan_json=original.model_dump_json())
    db.save_step(task["task_id"], 1, "旧步骤", "旧内容")

    async def fake_generate_plan(**_kwargs):
        return (
            ResearchPlan(
                title="新计划",
                steps=[ResearchStep(title="用户证据", description="补充访谈", need_search=True, step_type="research")],
            ),
            10,
            20,
        )

    monkeypatch.setattr("cli.agents.planner.generate_plan", fake_generate_plan)
    response = asyncio.run(
        revise_plan(
            task["task_id"],
            RevisePlanRequest(instruction="增加用户证据"),
            user={"user_id": db.LOCAL_DEFAULT_USER_ID},
        )
    )
    assert response.plan and response.plan["steps"][0]["title"] == "用户证据"
    assert db.list_steps(task["task_id"])[0]["title"] == "用户证据"
    assert response.budget.max_steps == 3


def test_report_follow_up_filters_unrecorded_links(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    from backend.app.api.routes.report import ask_report
    from backend.app.models.schemas import ReportQuestionRequest

    task = db.create_task("task_ask", "报告追问", user_id=db.LOCAL_DEFAULT_USER_ID)
    db.update_task(task["task_id"], status="completed", report_markdown="# 报告\n\n已有结论")
    step_id = db.save_step(task["task_id"], 1, "证据", "核对证据")
    db.update_step(
        step_id,
        sources_json=[{"title": "来源", "url": "https://example.com/source", "source_type": "web"}],
    )

    async def fake_generate_text(**_kwargs):
        return (
            "结论来自 [来源](https://example.com/source)，不是 [虚构](https://invalid.example/fake)。",
            12,
            8,
        )

    monkeypatch.setattr("cli.agents.base.LLMProvider.generate_text", fake_generate_text)
    result = asyncio.run(
        ask_report(
            task["task_id"],
            ReportQuestionRequest(question="关键证据是什么？"),
            user={"user_id": db.LOCAL_DEFAULT_USER_ID},
        )
    )
    assert "https://example.com/source" in result["answer_markdown"]
    assert "invalid.example" not in result["answer_markdown"]
    assert result["tokens"] == 20


def test_create_research_validates_and_returns_selected_knowledge(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    from backend.app.api.routes import research as research_routes
    from backend.app.main import app
    from backend.app.services import knowledge
    from backend.app.services.embedding import LocalHashEmbeddingService

    monkeypatch.setattr(research_routes, "require_research_providers", lambda: None)
    monkeypatch.setattr(research_routes, "enqueue_job", lambda *args, **kwargs: "job_test")
    monkeypatch.setattr(knowledge, "get_embedding_service", lambda: LocalHashEmbeddingService())

    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={"username": "rag_selection_user", "password": "password123"},
        )
        assert registered.status_code == 201
        token = registered.json()["access_token"]
        user_id = registered.json()["user"]["user_id"]
        headers = {"Authorization": f"Bearer {token}"}

        document = knowledge.queue_text_document(
            title="Selected RAG document",
            content="DeepFlow selected private knowledge." * 30,
            user_id=user_id,
        )
        knowledge.process_pending_document(document["doc_id"], user_id)

        created = client.post(
            "/api/research-tasks",
            headers=headers,
            json={
                "topic": "Use only the selected private document for this research",
                "knowledge_enabled": True,
                "knowledge_document_ids": [document["doc_id"]],
            },
        )

        assert created.status_code == 201, created.text
        payload = created.json()
        assert payload["knowledge_enabled"] is True
        assert payload["knowledge_document_ids"] == [document["doc_id"]]


def test_placeholder_provider_key_is_not_usable():
    from cli.tools.web_search import _usable_key

    assert _usable_key("tvly-real-value")
    assert not _usable_key("your-serpapi-api-key")
    assert not _usable_key("")


def test_completed_task_progress_uses_percentage_scale():
    response = _task_response(
        {
            "task_id": "task_progress",
            "topic": "Progress",
            "locale": "zh-CN",
            "status": "completed",
            "current_step": 2,
            "total_steps": 2,
            "report_markdown": "# Done",
            "clarification_json": "[]",
            "retryable": 0,
            "created_at": "2026-07-26T00:00:00",
            "updated_at": "2026-07-26T00:00:00",
        }
    )

    assert response.progress == 100.0
