from fastapi.testclient import TestClient

from backend.app.core import db
from backend.app.main import app


def test_http_errors_have_stable_machine_readable_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api-errors.db")
    with TestClient(app) as client:
        response = client.get("/api/auth/me")

    assert response.status_code == 401
    payload = response.json()
    assert payload["error_code"] == "authentication_required"
    assert payload["message"] == "Authentication required"
    assert payload["detail"] == "Authentication required"
