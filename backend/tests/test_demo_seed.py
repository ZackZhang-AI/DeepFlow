import json

from fastapi.testclient import TestClient

from backend.app.core import db
from backend.app.main import app
from backend.app.repositories.research import create_task
from backend.app.services.demo_seed import seed_demo_data


def _table_count(table: str) -> int:
    with db.get_connection() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_demo_seed_is_disabled_by_default(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "demo_disabled.db"
    monkeypatch.delenv("DEMO_SEED_ENABLED", raising=False)
    db.init_db()

    assert seed_demo_data() is False
    assert _table_count("research_tasks") == 0


def test_demo_seed_is_idempotent_and_preserves_regular_data(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "demo_idempotent.db"
    monkeypatch.setenv("DEMO_SEED_ENABLED", "true")
    db.init_db()
    create_task(
        "ordinary_task",
        "A regular user task",
        user_id=db.LOCAL_DEFAULT_USER_ID,
    )

    assert seed_demo_data() is True
    first_counts = {
        table: _table_count(table)
        for table in (
            "research_tasks",
            "research_steps",
            "research_events",
            "report_versions",
            "agent_runs",
            "knowledge_documents",
            "knowledge_chunks",
            "shared_links",
        )
    }
    assert seed_demo_data() is True
    second_counts = {table: _table_count(table) for table in first_counts}

    assert second_counts == first_counts
    assert first_counts == {
        "research_tasks": 3,
        "research_steps": 4,
        "research_events": 6,
        "report_versions": 2,
        "agent_runs": 6,
        "knowledge_documents": 1,
        "knowledge_chunks": 2,
        "shared_links": 1,
    }
    with db.get_connection() as conn:
        ordinary = conn.execute(
            "SELECT topic, is_demo FROM research_tasks WHERE task_id = 'ordinary_task'"
        ).fetchone()
        demos = conn.execute(
            "SELECT task_id, is_demo FROM research_tasks WHERE is_demo = 1 ORDER BY task_id"
        ).fetchall()
    assert dict(ordinary) == {"topic": "A regular user task", "is_demo": 0}
    assert [row["task_id"] for row in demos] == [
        "demo_market_research",
        "demo_private_rag_research",
    ]


def test_demo_seed_does_not_overwrite_conflicting_task(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "demo_conflict.db"
    monkeypatch.setenv("DEMO_SEED_ENABLED", "true")
    db.init_db()
    create_task(
        "demo_market_research",
        "User-owned task with a colliding ID",
        user_id=db.LOCAL_DEFAULT_USER_ID,
    )

    seed_demo_data()

    with db.get_connection() as conn:
        task = conn.execute(
            "SELECT topic, user_id, is_demo FROM research_tasks WHERE task_id = ?",
            ("demo_market_research",),
        ).fetchone()
        public_share = conn.execute(
            "SELECT 1 FROM shared_links WHERE resource_id = ?",
            ("demo_market_research",),
        ).fetchone()
    assert dict(task) == {
        "topic": "User-owned task with a colliding ID",
        "user_id": db.LOCAL_DEFAULT_USER_ID,
        "is_demo": 0,
    }
    assert public_share is None


def test_public_demo_share_filters_sources_and_private_content(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "demo_api.db"
    monkeypatch.setenv("DEMO_SEED_ENABLED", "true")
    monkeypatch.setenv("DEMO_SHARE_TOKEN", "deepflow-showcase")
    monkeypatch.setenv("DEMO_USERNAME", "interviewer")
    monkeypatch.setenv("DEMO_PASSWORD", "password123")

    with TestClient(app) as client:
        response = client.get("/api/shared/deepflow-showcase")
        missing = client.get("/api/shared/not-a-real-demo-token")
        login = client.post(
            "/api/auth/login",
            json={"username": "interviewer", "password": "password123"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        tasks = client.get("/api/research-tasks", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["readonly"] is True
    assert payload["resource"]["is_demo"] is True
    assert payload["resource"]["tokens_used"] == 18053
    assert len(payload["resource"]["sources"]) == 4
    assert all(set(source) == {"title", "url", "source_type"} for source in payload["resource"]["sources"])
    assert all(source["url"].startswith(("http://", "https://")) for source in payload["resource"]["sources"])
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "user_id" not in serialized
    assert "kb://" not in serialized
    assert "demo_private_chunk" not in serialized
    assert "document_content" not in serialized
    assert missing.status_code == 404

    assert tasks.status_code == 200, tasks.text
    task_by_id = {task["task_id"]: task for task in tasks.json()}
    assert task_by_id["demo_market_research"]["is_demo"] is True
    assert task_by_id["demo_private_rag_research"]["is_demo"] is True
    assert task_by_id["demo_private_rag_research"]["knowledge_enabled"] is True
    assert task_by_id["demo_private_rag_research"]["knowledge_document_ids"] == [
        "demo_private_product_brief"
    ]


def test_is_demo_migration_defaults_existing_tasks_to_false(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "legacy_is_demo.db"
    db.init_db()
    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO research_tasks
               (task_id, user_id, topic, created_at, updated_at, is_demo)
               VALUES ('legacy_task', 'local_default_user', 'Legacy', '2026-01-01', '2026-01-01', 0)"""
        )
        conn.execute("ALTER TABLE research_tasks DROP COLUMN is_demo")
        conn.commit()

    db.init_db()

    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT is_demo FROM research_tasks WHERE task_id = 'legacy_task'"
        ).fetchone()
    assert row["is_demo"] == 0
