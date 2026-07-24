from __future__ import annotations

from datetime import datetime, timedelta

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
