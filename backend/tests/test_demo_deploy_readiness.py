from fastapi.testclient import TestClient

from backend.app.core import db
from backend.app.core.rate_limit import reset_rate_limits
from backend.app.main import app


def _register(client: TestClient, username: str = "deploy_user") -> str:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_db_path_can_be_overridden_by_environment(monkeypatch, tmp_path):
    target = tmp_path / "persistent" / "deepflow.db"
    monkeypatch.setattr(db, "DB_PATH", None)
    monkeypatch.setenv("DEEPFLOW_DB_PATH", str(target))

    db.init_db()

    assert target.exists()
    assert db.get_db_path() == target


def test_demo_user_is_created_and_public_registration_can_be_disabled(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "deepflow_demo.db"
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "false")
    monkeypatch.setenv("DEMO_USERNAME", "interviewer")
    monkeypatch.setenv("DEMO_PASSWORD", "password123")

    with TestClient(app) as client:
        register = client.post(
            "/api/auth/register",
            json={"username": "blocked_user", "password": "password123"},
        )
        assert register.status_code == 403

        login = client.post(
            "/api/auth/login",
            json={"username": "interviewer", "password": "password123"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["user"]["username"] == "interviewer"


def test_sandbox_tool_test_endpoint_can_be_disabled(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "deepflow_sandbox_disabled.db"
    monkeypatch.setenv("DISABLE_SANDBOX_TOOL", "true")

    with TestClient(app) as client:
        token = _register(client, "sandbox_demo")
        response = client.post(
            "/api/tools/python_sandbox/test",
            json={"input": {"code": "print(1 + 1)"}},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()


def test_tool_test_rate_limit_returns_429(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "deepflow_rate_limit.db"
    reset_rate_limits()
    monkeypatch.setenv("TOOL_TEST_RATE_LIMIT_PER_HOUR", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "3600")

    with TestClient(app) as client:
        token = _register(client, "limited_tool_user")
        headers = {"Authorization": f"Bearer {token}"}

        first = client.post(
            "/api/tools/python_sandbox/test",
            json={"input": {"code": "print(1)"}},
            headers=headers,
        )
        second = client.post(
            "/api/tools/python_sandbox/test",
            json={"input": {"code": "print(2)"}},
            headers=headers,
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 429
    assert "rate limit" in second.json()["detail"].lower()


def test_uploaded_knowledge_document_size_limit(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "deepflow_upload_limit.db"
    monkeypatch.setenv("KNOWLEDGE_UPLOAD_MAX_BYTES", "8")

    with TestClient(app) as client:
        token = _register(client, "upload_limit_user")
        response = client.post(
            "/api/knowledge-documents/upload",
            files={"file": ("too-large.txt", b"0123456789", "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()
