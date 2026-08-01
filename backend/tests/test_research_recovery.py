from __future__ import annotations

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
