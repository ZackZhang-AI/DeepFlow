"""Idempotent, provider-free data for the public DeepFlow showcase."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.core.db import get_connection
from backend.app.core.runtime_config import demo_seed_enabled, demo_share_token

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "demo_seed.json"
DEMO_USER_ID = "demo_user"
DEMO_MARKER = "deepflow-demo-fixture-v1"
FIXED_TIMESTAMP = "2026-07-01T09:00:00+08:00"


def seed_demo_data() -> bool:
    """Seed both showcase tasks when enabled; never call external providers."""
    if not demo_seed_enabled():
        return False
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    with get_connection() as conn:
        _ensure_locked_demo_owner(conn)
        _seed_market_sample(conn, fixture["market"])
        _seed_rag_sample(conn, fixture["rag"])
        conn.commit()
    return True


def _ensure_locked_demo_owner(conn) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO users (user_id, username, password_hash, created_at)
           VALUES (?, ?, '', ?)""",
        (DEMO_USER_ID, "deepflow_demo", FIXED_TIMESTAMP),
    )


def _task_conflicts(conn, task_id: str) -> bool:
    row = conn.execute(
        "SELECT user_id, is_demo FROM research_tasks WHERE task_id = ?", (task_id,)
    ).fetchone()
    return bool(row and (row["user_id"] != DEMO_USER_ID or not row["is_demo"]))


def _insert_task(
    conn, *, task_id: str, topic: str, report: str, knowledge_ids: list[str], usage: dict,
) -> bool:
    if _task_conflicts(conn, task_id):
        return False
    conn.execute(
        """INSERT OR IGNORE INTO research_tasks
           (task_id, user_id, topic, locale, status, plan_json, report_markdown,
            current_step, total_steps, sources_count, search_calls, crawl_calls, search_credits,
            prompt_tokens, completion_tokens, tokens_used, cost_rmb, elapsed_seconds,
            knowledge_enabled, knowledge_document_ids_json, budget_profile, max_steps,
            max_search_calls_per_step, max_crawl_pages_per_step, max_tokens_budget,
            search_depth, planner_model, researcher_model, reporter_model, pricing_version,
            is_demo, created_at, updated_at)
           VALUES (?, ?, ?, 'zh-CN', 'completed', ?, ?, 2, 2, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, 'fast', 3, 1, 1, 50000,
                   'basic', 'demo-fixture', 'demo-fixture', 'demo-fixture', ?, 1, ?, ?)""",
        (
            task_id,
            DEMO_USER_ID,
            topic,
            json.dumps({"title": "演示研究计划", "steps": ["证据整理", "结论汇总"]}, ensure_ascii=False),
            report,
            0 if knowledge_ids else 4,
            int(usage.get("search_calls", 0)),
            int(usage.get("crawl_calls", 0)),
            int(usage.get("search_credits", 0)),
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
            int(usage.get("tokens_used", 0)),
            float(usage.get("cost_rmb", 0.0)),
            float(usage.get("elapsed_seconds", 0.0)),
            1 if knowledge_ids else 0,
            json.dumps(knowledge_ids, ensure_ascii=False),
            DEMO_MARKER,
            FIXED_TIMESTAMP,
            FIXED_TIMESTAMP,
        ),
    )
    return True


def _seed_market_sample(conn, sample: dict) -> None:
    task_id = sample["task_id"]
    if not _insert_task(
        conn, task_id=task_id, topic=sample["topic"], report=sample["report_markdown"],
        knowledge_ids=[], usage=sample["usage"],
    ):
        return
    _insert_step(conn, task_id, 0, "市场证据整理", sample["sources"])
    _insert_step(conn, task_id, 1, "产品价值分析", [])
    _insert_task_records(conn, task_id, "公开市场研究演示")
    conn.execute(
        """INSERT OR IGNORE INTO shared_links
           (share_id, token, user_id, resource_type, resource_id, created_at)
           VALUES ('demo_market_share', ?, ?, 'task_report', ?, ?)""",
        (demo_share_token(), DEMO_USER_ID, task_id, FIXED_TIMESTAMP),
    )


def _seed_rag_sample(conn, sample: dict) -> None:
    task_id = sample["task_id"]
    doc_id = sample["doc_id"]
    doc = conn.execute("SELECT user_id FROM knowledge_documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if doc and doc["user_id"] != DEMO_USER_ID:
        return
    if not _insert_task(
        conn, task_id=task_id, topic=sample["topic"], report=sample["report_markdown"],
        knowledge_ids=[doc_id], usage=sample["usage"],
    ):
        return
    conn.execute(
        """INSERT OR IGNORE INTO knowledge_documents
           (doc_id, user_id, title, content, source_name, source_type, status,
            chunk_count, metadata_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'demo-product-brief.md', 'markdown', 'ready', ?, ?, ?, ?)""",
        (doc_id, DEMO_USER_ID, sample["document_title"], sample["document_content"],
         len(sample["chunks"]), json.dumps({"is_demo": True, "fixture": DEMO_MARKER}),
         FIXED_TIMESTAMP, FIXED_TIMESTAMP),
    )
    for chunk in sample["chunks"]:
        conn.execute(
            """INSERT OR IGNORE INTO knowledge_chunks
               (chunk_id, doc_id, user_id, chunk_index, content, page_num, source_name,
                embedding_json, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'demo-product-brief.md', '[0.1, 0.2, 0.3]', ?, ?)""",
            (chunk["chunk_id"], doc_id, DEMO_USER_ID, chunk["chunk_index"], chunk["content"],
             chunk["page_num"], json.dumps({"is_demo": True}), FIXED_TIMESTAMP),
        )
    kb_sources = [{"title": sample["document_title"], "url": f"kb://{doc_id}#{chunk['chunk_id']}", "source_type": "knowledge"} for chunk in sample["chunks"]]
    _insert_step(conn, task_id, 0, "私域资料检索", kb_sources)
    _insert_step(conn, task_id, 1, "能力边界总结", [])
    _insert_task_records(conn, task_id, "私域 RAG 研究演示")


def _insert_step(conn, task_id: str, index: int, title: str, sources: list[dict]) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO research_steps
           (step_id, task_id, user_id, step_index, title, description, need_search,
            status, findings_markdown, conclusion, sources_json)
           VALUES (?, ?, ?, ?, ?, '固定脱敏演示步骤', 1, 'completed', ?, ?, ?)""",
        (f"{task_id}_step_{index}", task_id, DEMO_USER_ID, index, title,
         f"已完成：{title}", f"{title}结论已纳入演示报告。",
         json.dumps(sources, ensure_ascii=False)),
    )


def _insert_task_records(conn, task_id: str, label: str) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO report_versions
           (version_id, task_id, user_id, content_markdown, change_note, created_at)
           SELECT ?, task_id, user_id, report_markdown, '固定演示版本', ?
           FROM research_tasks WHERE task_id = ?""",
        (f"ver_{task_id}", FIXED_TIMESTAMP, task_id),
    )
    runs = [
        (f"run_{task_id}_planner", "Planner", "planning", "生成固定演示计划", 900, 300, 1.2),
        (f"run_{task_id}_researcher", "Researcher", "researching", label, 2200, 700, 12.4),
        (f"run_{task_id}_reporter", "Reporter", "generating_report", "生成固定演示报告", 1100, 800, 5.8),
    ]
    for run_id, agent, phase, summary, prompt, completion, elapsed in runs:
        conn.execute(
            """INSERT OR IGNORE INTO agent_runs
               (run_id, task_id, user_id, agent_name, phase, status, input_summary,
                output_summary, tool_calls_json, prompt_tokens, completion_tokens,
                elapsed_seconds, error, created_at)
               VALUES (?, ?, ?, ?, ?, 'completed', '脱敏演示输入', ?, '[]', ?, ?, ?, '', ?)""",
            (run_id, task_id, DEMO_USER_ID, agent, phase, summary, prompt, completion, elapsed, FIXED_TIMESTAMP),
        )
    existing = conn.execute(
        "SELECT 1 FROM research_events WHERE task_id = ? LIMIT 1", (task_id,)
    ).fetchone()
    if not existing:
        for event_type, data in (
            ("planner.completed", {"message": "演示计划已生成"}),
            ("research.completed", {"message": label}),
            ("report.completed", {"message": "演示报告已生成"}),
        ):
            conn.execute(
                """INSERT INTO research_events
                   (task_id, user_id, event_type, data_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, DEMO_USER_ID, event_type, json.dumps(data, ensure_ascii=False), FIXED_TIMESTAMP),
            )
