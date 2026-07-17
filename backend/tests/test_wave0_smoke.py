import json
import time

from fastapi.testclient import TestClient

from backend.app.core import db
from backend.app.main import app
from backend.app.services import knowledge as knowledge_service


class FakeEmbeddingService:
    def _vector(self, text: str) -> list[float]:
        value = sum(ord(ch) for ch in text) % 997
        return [float(value), float(len(text) % 101), 1.0]

    def embed_documents(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FakeRerankService:
    def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        ranked = sorted(
            enumerate(documents),
            key=lambda item: item[1].count(query[:2]) + len(set(query) & set(item[1])),
            reverse=True,
        )
        return [(index, 1.0 - rank * 0.01) for rank, (index, _) in enumerate(ranked[:top_n])]


def _unique_username(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}"


def _register(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_auth_knowledge_report_and_artifact_smoke(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "deepflow_test.db"
    monkeypatch.setattr(knowledge_service, "get_embedding_service", lambda: FakeEmbeddingService())
    monkeypatch.setattr(knowledge_service, "get_rerank_service", lambda: FakeRerankService())

    with TestClient(app) as client:
        assert client.get("/api/auth/me").status_code == 401

        token_a = _register(client, _unique_username("wave0_a"))
        token_b = _register(client, _unique_username("wave0_b"))
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        task = client.post(
            "/api/research-tasks",
            json={
                "topic": "DeepFlow Wave0 smoke test topic with enough detail for planning",
                "max_steps": 3,
            },
            headers=headers_a,
        )
        assert task.status_code == 201, task.text
        task_id = task.json()["task_id"]
        assert client.get(f"/api/research-tasks/{task_id}", headers=headers_a).status_code == 200
        assert client.get(f"/api/research-tasks/{task_id}", headers=headers_b).status_code == 404

        doc = client.post(
            "/api/knowledge-documents",
            json={
                "title": "DeepFlow RAG smoke",
                "content": "DeepFlow supports private knowledge retrieval with traceable chunks.",
                "source_name": "smoke.md",
                "source_type": "text",
            },
            headers=headers_a,
        )
        assert doc.status_code == 200, doc.text
        assert doc.json()["status"] in {"ready", "completed"}

        search = client.get("/api/knowledge-documents/search?q=private knowledge&rerank=true", headers=headers_a)
        assert search.status_code == 200, search.text
        hits = search.json()
        assert hits
        assert {"doc_id", "chunk_id", "score", "page_num", "retrieval_mode"} <= set(hits[0])

        db.update_task(
            task_id,
            owner_user_id=client.get("/api/auth/me", headers=headers_a).json()["user_id"],
            status="completed",
            report_markdown="# Smoke Report\n\nSource: kb://doc#chunk\n",
            sources_count=1,
        )
        report = client.get(f"/api/reports/{task_id}", headers=headers_a)
        assert report.status_code == 200, report.text

        md = client.get(f"/api/reports/{task_id}/download?format=markdown", headers=headers_a)
        assert md.status_code == 200, md.text
        assert "Smoke Report" in md.text

        artifact = db.save_artifact(
            artifact_id="art_smoke",
            task_id=task_id,
            artifact_type="ppt",
            title="Smoke Artifact",
            content="# Slide\n\nSmoke",
            metadata={"format": "markdown"},
            user_id=client.get("/api/auth/me", headers=headers_a).json()["user_id"],
        )
        assert artifact["artifact_id"] == "art_smoke"
        artifact_download = client.get("/api/artifacts/download/art_smoke", headers=headers_a)
        assert artifact_download.status_code == 200, artifact_download.text
        assert "Smoke" in artifact_download.text

        assert client.get("/api/artifacts/download/art_smoke", headers=headers_b).status_code == 404


def test_prd_extension_smoke(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "deepflow_prd_extensions.db"
    monkeypatch.setattr(knowledge_service, "get_embedding_service", lambda: FakeEmbeddingService())
    monkeypatch.setattr(knowledge_service, "get_rerank_service", lambda: FakeRerankService())

    with TestClient(app) as client:
        username_a = _unique_username("prd_a")
        username_b = _unique_username("prd_b")
        token_a = _register(client, username_a)
        token_b = _register(client, username_b)
        user_a = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"}).json()
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        tools = client.get("/api/tools", headers=headers_a)
        assert tools.status_code == 200, tools.text
        assert {tool["tool_id"] for tool in tools.json()} >= {"web_search", "knowledge_search", "python_sandbox"}
        sandbox = client.post(
            "/api/tools/python_sandbox/test",
            json={"input": {"code": "print(1 + 1)", "timeout": 5}},
            headers=headers_a,
        )
        assert sandbox.status_code == 200, sandbox.text
        assert sandbox.json()["success"] is True
        assert "2" in sandbox.json()["output_summary"]

        workspace = client.post(
            "/api/workspaces",
            json={"name": "PRD Smoke Workspace", "description": "team space"},
            headers=headers_a,
        )
        assert workspace.status_code == 201, workspace.text
        workspace_id = workspace.json()["workspace_id"]
        assert client.get(f"/api/workspaces/{workspace_id}", headers=headers_b).status_code == 404

        member = client.post(
            f"/api/workspaces/{workspace_id}/members",
            json={"username": username_b, "role": "viewer"},
            headers=headers_a,
        )
        assert member.status_code == 200, member.text
        assert client.get(f"/api/workspaces/{workspace_id}", headers=headers_b).status_code == 200
        viewer_project = client.post(
            f"/api/workspaces/{workspace_id}/projects",
            json={"name": "Viewer Project"},
            headers=headers_b,
        )
        assert viewer_project.status_code == 403
        project = client.post(
            f"/api/workspaces/{workspace_id}/projects",
            json={"name": "Owner Project"},
            headers=headers_a,
        )
        assert project.status_code == 201, project.text

        task_id = "task_prd_ext"
        db.create_task(task_id, "PRD extension task", "zh-CN", user_id=user_a["user_id"])
        db.update_task(
            task_id,
            owner_user_id=user_a["user_id"],
            status="completed",
            report_markdown="# PRD Extension Report\n\nBody",
            sources_count=0,
        )
        comment = client.post(
            "/api/workspaces/comments",
            json={"task_id": task_id, "anchor": "summary", "content": "Looks good"},
            headers=headers_a,
        )
        assert comment.status_code == 201, comment.text
        comments = client.get(f"/api/workspaces/comments/{task_id}", headers=headers_a)
        assert comments.status_code == 200, comments.text
        assert comments.json()[0]["content"] == "Looks good"
        share = client.post(
            "/api/share-links",
            json={"resource_type": "task_report", "resource_id": task_id},
            headers=headers_a,
        )
        assert share.status_code == 201, share.text
        shared = client.get(f"/api/shared/{share.json()['token']}")
        assert shared.status_code == 200, shared.text
        assert shared.json()["readonly"] is True

        template = client.post(
            "/api/templates",
            json={
                "name": "Market Scan",
                "category": "market",
                "description": "PRD template",
                "clarification_questions": ["目标市场是什么？"],
                "plan_structure": [{"title": "市场概览", "description": "size", "need_search": True}],
                "recommended_domains": ["example.com"],
                "report_style": "market",
            },
            headers=headers_a,
        )
        assert template.status_code == 201, template.text
        template_id = template.json()["template_id"]
        started = client.post(
            f"/api/templates/{template_id}/start-research",
            json={"topic": "AI research platform market", "locale": "zh-CN"},
            headers=headers_a,
        )
        assert started.status_code == 201, started.text
        assert started.json()["status"] == "awaiting_confirmation"

        workflow = client.post(
            "/api/workflows",
            json={
                "name": "Simple PRD Workflow",
                "description": "planner reporter",
                "nodes": [
                    {"id": "plan", "type": "Planner", "config": {"plan": ["research", "report"]}},
                    {"id": "report", "type": "Reporter", "config": {}},
                ],
                "edges": [{"from": "plan", "to": "report"}],
                "budget": {"max_steps": 3, "retries": 0},
            },
            headers=headers_a,
        )
        assert workflow.status_code == 201, workflow.text
        workflow_id = workflow.json()["workflow_id"]
        run = client.post(
            f"/api/workflows/{workflow_id}/runs",
            json={"input": {"topic": "PRD workflow smoke"}},
            headers=headers_a,
        )
        assert run.status_code == 201, run.text
        assert run.json()["status"] == "completed"
        trace = client.get(f"/api/workflows/runs/{run.json()['run_id']}/trace", headers=headers_a)
        assert trace.status_code == 200, trace.text
        assert [item["node_type"] for item in trace.json()] == ["Planner", "Reporter"]
