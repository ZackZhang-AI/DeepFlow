"""SQLite persistence for DeepFlow."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.app.config import BACKEND_DIR
from backend.app.core.runtime_config import database_path

DEFAULT_DB_PATH = BACKEND_DIR / "deepflow.db"
DB_PATH: Path | None = None
LOCAL_DEFAULT_USER_ID = "local_default_user"


def get_db_path() -> Path:
    path = Path(DB_PATH) if DB_PATH is not None else database_path(DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS user_tool_settings (
            user_id TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, tool_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS research_tasks (
            task_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'local_default_user',
            topic TEXT NOT NULL,
            locale TEXT DEFAULT 'zh-CN',
            status TEXT DEFAULT 'init',
            plan_json TEXT,
            report_markdown TEXT,
            current_step INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 0,
            sources_count INTEGER DEFAULT 0,
            search_calls INTEGER DEFAULT 0,
            crawl_calls INTEGER DEFAULT 0,
            search_credits INTEGER DEFAULT 0,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            cost_rmb REAL DEFAULT 0.0,
            elapsed_seconds REAL DEFAULT 0.0,
            errors_json TEXT DEFAULT '[]',
            clarification_json TEXT DEFAULT '[]',
            search_domains_json TEXT DEFAULT '[]',
            recency_days INTEGER,
            budget_profile TEXT DEFAULT 'fast',
            max_steps INTEGER DEFAULT 3,
            max_search_calls_per_step INTEGER DEFAULT 1,
            max_crawl_pages_per_step INTEGER DEFAULT 1,
            max_tokens_budget INTEGER DEFAULT 30000,
            search_depth TEXT DEFAULT 'basic',
            planner_model TEXT DEFAULT 'deepseek-v4-flash',
            researcher_model TEXT DEFAULT 'deepseek-v4-flash',
            reporter_model TEXT DEFAULT 'deepseek-v4-flash',
            pricing_version TEXT DEFAULT '',
            attempt_count INTEGER DEFAULT 0,
            error_code TEXT DEFAULT '',
            error_message TEXT DEFAULT '',
            retryable INTEGER DEFAULT 0,
            last_heartbeat_at TEXT,
            failed_phase TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS background_jobs (
            job_id TEXT PRIMARY KEY,
            task_id TEXT,
            user_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            payload_json TEXT DEFAULT '{}',
            attempt_count INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            run_after TEXT NOT NULL,
            locked_at TEXT,
            heartbeat_at TEXT,
            error_code TEXT DEFAULT '',
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_background_jobs_ready
            ON background_jobs(status, run_after, created_at);

        CREATE TABLE IF NOT EXISTS research_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            data_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES research_tasks(task_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_research_events_task_sequence
            ON research_events(task_id, sequence);

        CREATE TABLE IF NOT EXISTS research_steps (
            step_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local_default_user',
            step_index INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            need_search INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            findings_markdown TEXT,
            conclusion TEXT,
            sources_json TEXT DEFAULT '[]',
            FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
        );

        CREATE TABLE IF NOT EXISTS knowledge_documents (
            doc_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'local_default_user',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source_name TEXT,
            source_type TEXT DEFAULT 'text',
            status TEXT DEFAULT 'pending',
            chunk_count INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local_default_user',
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            page_num INTEGER,
            source_name TEXT DEFAULT '',
            embedding_json TEXT NOT NULL,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES knowledge_documents(doc_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc_id
            ON knowledge_chunks(doc_id);

        CREATE TABLE IF NOT EXISTS report_versions (
            version_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local_default_user',
            content_markdown TEXT NOT NULL,
            change_note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local_default_user',
            artifact_type TEXT NOT NULL,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            run_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'local_default_user',
            agent_name TEXT NOT NULL,
            phase TEXT NOT NULL,
            status TEXT NOT NULL,
            input_summary TEXT DEFAULT '',
            output_summary TEXT DEFAULT '',
            tool_calls_json TEXT DEFAULT '[]',
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            elapsed_seconds REAL DEFAULT 0.0,
            error TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (workspace_id, user_id),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS report_comments (
            comment_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            anchor TEXT DEFAULT '',
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES research_tasks(task_id)
        );

        CREATE TABLE IF NOT EXISTS shared_links (
            share_id TEXT PRIMARY KEY,
            token TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            revoked_at TEXT
        );

        CREATE TABLE IF NOT EXISTS research_templates (
            template_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT '',
            description TEXT DEFAULT '',
            clarification_questions_json TEXT DEFAULT '[]',
            plan_structure_json TEXT DEFAULT '[]',
            recommended_domains_json TEXT DEFAULT '[]',
            report_style TEXT DEFAULT 'general',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workflows (
            workflow_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            nodes_json TEXT NOT NULL,
            edges_json TEXT DEFAULT '[]',
            budget_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workflow_runs (
            run_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL,
            input_json TEXT DEFAULT '{}',
            outputs_json TEXT DEFAULT '{}',
            error TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS workflow_node_runs (
            node_run_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            node_type TEXT NOT NULL,
            status TEXT NOT NULL,
            input_summary TEXT DEFAULT '',
            output_summary TEXT DEFAULT '',
            tool_calls_json TEXT DEFAULT '[]',
            elapsed_seconds REAL DEFAULT 0.0,
            error TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id) ON DELETE CASCADE
        );
    """)
    _ensure_column(conn, "research_tasks", "search_calls", "INTEGER DEFAULT 0")
    _ensure_column(conn, "research_tasks", "crawl_calls", "INTEGER DEFAULT 0")
    _ensure_column(conn, "research_tasks", "clarification_json", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "research_tasks", "search_domains_json", "TEXT DEFAULT '[]'")
    _ensure_column(conn, "research_tasks", "recency_days", "INTEGER")
    _ensure_column(conn, "research_tasks", "user_id", f"TEXT DEFAULT '{LOCAL_DEFAULT_USER_ID}'")
    _ensure_column(conn, "research_steps", "user_id", f"TEXT DEFAULT '{LOCAL_DEFAULT_USER_ID}'")
    _ensure_column(conn, "knowledge_documents", "user_id", f"TEXT DEFAULT '{LOCAL_DEFAULT_USER_ID}'")
    _ensure_column(conn, "knowledge_chunks", "user_id", f"TEXT DEFAULT '{LOCAL_DEFAULT_USER_ID}'")
    _ensure_column(conn, "knowledge_documents", "status", "TEXT DEFAULT 'pending'")
    _ensure_column(conn, "knowledge_documents", "chunk_count", "INTEGER DEFAULT 0")
    _ensure_column(conn, "knowledge_documents", "error_message", "TEXT DEFAULT ''")
    _ensure_column(conn, "knowledge_documents", "metadata_json", "TEXT DEFAULT '{}'")
    _ensure_column(conn, "report_versions", "user_id", f"TEXT DEFAULT '{LOCAL_DEFAULT_USER_ID}'")
    _ensure_column(conn, "artifacts", "user_id", f"TEXT DEFAULT '{LOCAL_DEFAULT_USER_ID}'")
    _ensure_column(conn, "agent_runs", "user_id", f"TEXT DEFAULT '{LOCAL_DEFAULT_USER_ID}'")
    _ensure_column(conn, "research_tasks", "workspace_id", "TEXT")
    _ensure_column(conn, "research_tasks", "project_id", "TEXT")
    _ensure_column(conn, "research_tasks", "attempt_count", "INTEGER DEFAULT 0")
    _ensure_column(conn, "research_tasks", "error_code", "TEXT DEFAULT ''")
    _ensure_column(conn, "research_tasks", "error_message", "TEXT DEFAULT ''")
    _ensure_column(conn, "research_tasks", "retryable", "INTEGER DEFAULT 0")
    _ensure_column(conn, "research_tasks", "last_heartbeat_at", "TEXT")
    _ensure_column(conn, "research_tasks", "failed_phase", "TEXT DEFAULT ''")
    _ensure_column(conn, "research_tasks", "max_steps", "INTEGER DEFAULT 5")
    _ensure_column(conn, "research_tasks", "budget_profile", "TEXT DEFAULT 'fast'")
    _ensure_column(conn, "research_tasks", "max_search_calls_per_step", "INTEGER DEFAULT 1")
    _ensure_column(conn, "research_tasks", "max_crawl_pages_per_step", "INTEGER DEFAULT 1")
    _ensure_column(conn, "research_tasks", "max_tokens_budget", "INTEGER DEFAULT 30000")
    _ensure_column(conn, "research_tasks", "search_depth", "TEXT DEFAULT 'basic'")
    _ensure_column(conn, "research_tasks", "search_credits", "INTEGER DEFAULT 0")
    _ensure_column(conn, "research_tasks", "prompt_tokens", "INTEGER DEFAULT 0")
    _ensure_column(conn, "research_tasks", "completion_tokens", "INTEGER DEFAULT 0")
    _ensure_column(conn, "research_tasks", "planner_model", "TEXT DEFAULT 'deepseek-v4-flash'")
    _ensure_column(conn, "research_tasks", "researcher_model", "TEXT DEFAULT 'deepseek-v4-flash'")
    _ensure_column(conn, "research_tasks", "reporter_model", "TEXT DEFAULT 'deepseek-v4-flash'")
    _ensure_column(conn, "research_tasks", "pricing_version", "TEXT DEFAULT ''")
    _ensure_column(conn, "knowledge_documents", "workspace_id", "TEXT")
    _ensure_column(conn, "knowledge_documents", "project_id", "TEXT")
    _ensure_column(conn, "artifacts", "workspace_id", "TEXT")
    _ensure_column(conn, "artifacts", "project_id", "TEXT")
    _ensure_column(conn, "report_versions", "workspace_id", "TEXT")
    _ensure_column(conn, "report_versions", "project_id", "TEXT")
    _ensure_column(conn, "shared_links", "expires_at", "TEXT")
    _ensure_column(conn, "shared_links", "revoked_at", "TEXT")
    _ensure_column(conn, "shared_links", "workspace_id", "TEXT")
    conn.execute(
        """UPDATE research_tasks
           SET budget_profile = CASE
                   WHEN max_steps <= 3 THEN 'fast'
                   WHEN max_steps <= 5 THEN 'standard'
                   ELSE 'deep'
               END,
               max_search_calls_per_step = CASE
                   WHEN max_steps <= 3 THEN 1
                   WHEN max_steps <= 5 THEN 2
                   ELSE 3
               END,
               max_crawl_pages_per_step = CASE
                   WHEN max_steps <= 3 THEN 1
                   WHEN max_steps <= 5 THEN 2
                   ELSE 3
               END,
               max_tokens_budget = CASE
                   WHEN max_steps <= 3 THEN 30000
                   WHEN max_steps <= 5 THEN 60000
                   ELSE 100000
               END,
               search_depth = CASE WHEN max_steps > 5 THEN 'advanced' ELSE 'basic' END
           WHERE pricing_version IS NULL OR pricing_version = ''"""
    )
    conn.execute(
        """UPDATE research_tasks
           SET max_tokens_budget = CASE budget_profile
                   WHEN 'fast' THEN 30000
                   WHEN 'standard' THEN 60000
                   WHEN 'deep' THEN 100000
                   ELSE max_tokens_budget
               END,
               retryable = CASE
                   WHEN status = 'failed' AND error_code = 'budget_exceeded' THEN 1
                   ELSE retryable
               END
           WHERE (budget_profile = 'fast' AND max_tokens_budget = 20000)
              OR (budget_profile = 'standard' AND max_tokens_budget = 40000)
              OR (budget_profile = 'deep' AND max_tokens_budget = 70000)"""
    )
    conn.execute(
        """UPDATE artifacts
           SET workspace_id = (
                 SELECT workspace_id FROM research_tasks t WHERE t.task_id = artifacts.task_id
               ),
               project_id = (
                 SELECT project_id FROM research_tasks t WHERE t.task_id = artifacts.task_id
               )
           WHERE workspace_id IS NULL"""
    )
    conn.execute(
        """UPDATE report_versions
           SET workspace_id = (
                 SELECT workspace_id FROM research_tasks t WHERE t.task_id = report_versions.task_id
               ),
               project_id = (
                 SELECT project_id FROM research_tasks t WHERE t.task_id = report_versions.task_id
               )
           WHERE workspace_id IS NULL"""
    )
    conn.execute(
        """UPDATE shared_links
           SET workspace_id = CASE resource_type
               WHEN 'task_report' THEN (
                   SELECT workspace_id FROM research_tasks t
                   WHERE t.task_id = shared_links.resource_id
               )
               WHEN 'artifact' THEN (
                   SELECT workspace_id FROM artifacts a
                   WHERE a.artifact_id = shared_links.resource_id
               )
               END
           WHERE workspace_id IS NULL"""
    )
    _ensure_local_default_user(conn)
    for table in (
        "research_tasks",
        "research_steps",
        "knowledge_documents",
        "knowledge_chunks",
        "report_versions",
        "artifacts",
        "agent_runs",
    ):
        conn.execute(
            f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL OR user_id = ''",
            (LOCAL_DEFAULT_USER_ID,),
        )
    conn.commit()
    conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _ensure_local_default_user(conn: sqlite3.Connection) -> None:
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT OR IGNORE INTO users (user_id, username, password_hash, created_at)
           VALUES (?, ?, ?, ?)""",
        (LOCAL_DEFAULT_USER_ID, LOCAL_DEFAULT_USER_ID, "", now),
    )

_REPOSITORY_EXPORTS = {
    "create_auth_session": "backend.app.repositories.auth",
    "create_task": "backend.app.repositories.research",
    "create_user": "backend.app.repositories.auth",
    "delete_auth_session": "backend.app.repositories.auth",
    "delete_expired_auth_sessions": "backend.app.repositories.auth",
    "delete_knowledge_document": "backend.app.repositories.knowledge",
    "get_agent_run": "backend.app.repositories.research",
    "get_artifact": "backend.app.repositories.artifact",
    "get_auth_session": "backend.app.repositories.auth",
    "get_knowledge_document": "backend.app.repositories.knowledge",
    "get_report_version": "backend.app.repositories.artifact",
    "get_task": "backend.app.repositories.research",
    "get_tool_setting": "backend.app.repositories.tool",
    "get_user_by_id": "backend.app.repositories.auth",
    "get_user_by_username": "backend.app.repositories.auth",
    "list_agent_runs": "backend.app.repositories.research",
    "list_artifacts": "backend.app.repositories.artifact",
    "list_embedded_knowledge_chunks": "backend.app.repositories.knowledge",
    "list_knowledge_chunks": "backend.app.repositories.knowledge",
    "list_knowledge_documents": "backend.app.repositories.knowledge",
    "list_report_versions": "backend.app.repositories.artifact",
    "list_steps": "backend.app.repositories.research",
    "list_tasks": "backend.app.repositories.research",
    "replace_knowledge_chunks": "backend.app.repositories.knowledge",
    "save_agent_run": "backend.app.repositories.research",
    "save_artifact": "backend.app.repositories.artifact",
    "save_knowledge_document": "backend.app.repositories.knowledge",
    "save_report_version": "backend.app.repositories.artifact",
    "save_step": "backend.app.repositories.research",
    "set_tool_setting": "backend.app.repositories.tool",
    "update_knowledge_document": "backend.app.repositories.knowledge",
    "update_step": "backend.app.repositories.research",
    "update_task": "backend.app.repositories.research",
}


def __getattr__(name: str):
    """Keep legacy imports working while persistence lives in repositories."""
    module_name = _REPOSITORY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    return getattr(import_module(module_name), name)


__all__ = [
    "DB_PATH",
    "LOCAL_DEFAULT_USER_ID",
    "get_connection",
    "get_db_path",
    "init_db",
    *_REPOSITORY_EXPORTS,
]
