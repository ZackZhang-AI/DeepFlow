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


def test_workspace_roles_and_shared_resources_are_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "workspace_roles.db")
    with TestClient(app) as client:
        owner_token, owner = _register(client, "workspace_owner")
        editor_token, editor = _register(client, "workspace_editor")
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        editor_headers = {"Authorization": f"Bearer {editor_token}"}

        workspace = client.post(
            "/api/workspaces",
            json={"name": "Research team", "description": ""},
            headers=owner_headers,
        ).json()
        workspace_id = workspace["workspace_id"]

        add_editor = client.post(
            f"/api/workspaces/{workspace_id}/members",
            json={"username": editor["username"], "role": "editor"},
            headers=owner_headers,
        )
        assert add_editor.status_code == 200, add_editor.text

        cannot_add_owner = client.post(
            f"/api/workspaces/{workspace_id}/members",
            json={"username": editor["username"], "role": "owner"},
            headers=owner_headers,
        )
        assert cannot_add_owner.status_code == 409
        cannot_downgrade_owner = client.post(
            f"/api/workspaces/{workspace_id}/members",
            json={"username": owner["username"], "role": "viewer"},
            headers=owner_headers,
        )
        assert cannot_downgrade_owner.status_code == 409

        task = db.create_task(
            "task_workspace_editor",
            "workspace report",
            user_id=editor["user_id"],
            workspace_id=workspace_id,
        )
        db.update_task(task["task_id"], status="completed", report_markdown="# Team report")
        version_id = db.save_report_version(
            task["task_id"],
            "# Previous team report",
            user_id=editor["user_id"],
        )
        artifact = db.save_artifact(
            "artifact_workspace",
            task["task_id"],
            "podcast_script",
            "Team artifact",
            "# Script",
            user_id=editor["user_id"],
        )
        document = db.save_knowledge_document(
            "doc_workspace",
            "Team source",
            "Shared evidence",
            status="ready",
            user_id=editor["user_id"],
            workspace_id=workspace_id,
        )
        db.replace_knowledge_chunks(
            document["doc_id"],
            [
                {
                    "chunk_id": "chunk_workspace",
                    "chunk_index": 0,
                    "content": "Shared evidence",
                    "embedding": [1.0, 0.0],
                }
            ],
            user_id=editor["user_id"],
        )

        assert client.get(
            f"/api/artifacts/detail/{artifact['artifact_id']}",
            headers=owner_headers,
        ).status_code == 200
        assert client.get(
            f"/api/reports/versions/{version_id}",
            headers=owner_headers,
        ).status_code == 200
        listed_docs = client.get("/api/knowledge-documents", headers=owner_headers)
        assert document["doc_id"] in {item["doc_id"] for item in listed_docs.json()}
        assert client.get(
            f"/api/knowledge-documents/{document['doc_id']}/chunks",
            headers=owner_headers,
        ).status_code == 200

        downgrade = client.post(
            f"/api/workspaces/{workspace_id}/members",
            json={"username": editor["username"], "role": "viewer"},
            headers=owner_headers,
        )
        assert downgrade.status_code == 200
        edit_after_downgrade = client.patch(
            f"/api/reports/{task['task_id']}",
            json={"content_markdown": "# Viewer edit", "change_note": "must fail"},
            headers=editor_headers,
        )
        assert edit_after_downgrade.status_code == 403
        share_as_viewer = client.post(
            "/api/share-links",
            json={
                "resource_type": "task_report",
                "resource_id": task["task_id"],
                "expires_in_days": 7,
            },
            headers=editor_headers,
        )
        assert share_as_viewer.status_code == 403
