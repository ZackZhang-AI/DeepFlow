from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.app.core import db
from backend.app.main import app


def _register(client: TestClient, prefix: str) -> tuple[str, dict]:
    response = client.post(
        "/api/auth/register",
        json={"username": f"{prefix}_{uuid.uuid4().hex[:8]}", "password": "Passw0rd!234"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return data["access_token"], data["user"]


def test_logout_tool_isolation_and_share_revoke(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "collaboration.db")
    with TestClient(app) as client:
        token_a, user_a = _register(client, "collab_a")
        token_b, _ = _register(client, "collab_b")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        disabled = client.patch(
            "/api/tools/web_search",
            json={"enabled": False},
            headers=headers_a,
        )
        assert disabled.status_code == 200
        tools_b = client.get("/api/tools", headers=headers_b).json()
        assert next(tool for tool in tools_b if tool["tool_id"] == "web_search")["enabled"] is True

        task = db.create_task("task_shared", "shared report", user_id=user_a["user_id"])
        db.update_task(
            task["task_id"],
            report_markdown="# Shared",
            status="completed",
        )
        share = client.post(
            "/api/share-links",
            json={
                "resource_type": "task_report",
                "resource_id": task["task_id"],
                "expires_in_days": 7,
            },
            headers=headers_a,
        )
        assert share.status_code == 201, share.text
        share_data = share.json()
        assert client.get(f"/api/shared/{share_data['token']}").status_code == 200
        assert client.delete(f"/api/share-links/{share_data['share_id']}", headers=headers_a).status_code == 204
        assert client.get(f"/api/shared/{share_data['token']}").status_code == 404

        assert client.post("/api/auth/logout", headers=headers_a).status_code == 204
        assert client.get("/api/auth/me", headers=headers_a).status_code == 401
