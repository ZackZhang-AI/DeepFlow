"""SQLite persistence for DeepFlow."""

import json
import sqlite3
from datetime import datetime
from typing import Optional

from backend.app.config import BACKEND_DIR

DB_PATH = BACKEND_DIR / "deepflow.db"
LOCAL_DEFAULT_USER_ID = "local_default_user"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
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
            tokens_used INTEGER DEFAULT 0,
            cost_rmb REAL DEFAULT 0.0,
            elapsed_seconds REAL DEFAULT 0.0,
            errors_json TEXT DEFAULT '[]',
            clarification_json TEXT DEFAULT '[]',
            search_domains_json TEXT DEFAULT '[]',
            recency_days INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

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
            created_at TEXT NOT NULL
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
    _ensure_column(conn, "knowledge_documents", "workspace_id", "TEXT")
    _ensure_column(conn, "knowledge_documents", "project_id", "TEXT")
    _ensure_column(conn, "artifacts", "workspace_id", "TEXT")
    _ensure_column(conn, "artifacts", "project_id", "TEXT")
    _ensure_column(conn, "report_versions", "workspace_id", "TEXT")
    _ensure_column(conn, "report_versions", "project_id", "TEXT")
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


def create_user(user_id: str, username: str, password_hash: str) -> dict:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO users (user_id, username, password_hash, created_at)
           VALUES (?, ?, ?, ?)""",
        (user_id, username, password_hash, now),
    )
    conn.commit()
    conn.close()
    return get_user_by_id(user_id)


def get_user_by_id(user_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE lower(username) = lower(?)", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_auth_session(token_hash: str, user_id: str, expires_at: str) -> None:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO auth_sessions (token_hash, user_id, expires_at, created_at)
           VALUES (?, ?, ?, ?)""",
        (token_hash, user_id, expires_at, now),
    )
    conn.commit()
    conn.close()


def get_auth_session(token_hash: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM auth_sessions WHERE token_hash = ?", (token_hash,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _task_user_id(task_id: str) -> str:
    task = get_task(task_id)
    return (task or {}).get("user_id") or LOCAL_DEFAULT_USER_ID


def create_task(
    task_id: str,
    topic: str,
    locale: str = "zh-CN",
    search_domains: list[str] | None = None,
    recency_days: int | None = None,
    user_id: str = LOCAL_DEFAULT_USER_ID,
) -> dict:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO research_tasks
           (task_id, user_id, topic, locale, status, search_domains_json, recency_days, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'coordinating', ?, ?, ?, ?)""",
        (
            task_id,
            user_id,
            topic,
            locale,
            json.dumps(search_domains or [], ensure_ascii=False),
            recency_days,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return get_task(task_id)


def get_task(task_id: str, user_id: str | None = None) -> Optional[dict]:
    conn = get_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM research_tasks WHERE task_id = ?", (task_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM research_tasks WHERE task_id = ? AND user_id = ?",
            (task_id, user_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_task(task_id: str, owner_user_id: str | None = None, **kwargs) -> Optional[dict]:
    kwargs["updated_at"] = datetime.now().isoformat()
    if "errors_json" in kwargs and isinstance(kwargs["errors_json"], list):
        kwargs["errors_json"] = json.dumps(kwargs["errors_json"], ensure_ascii=False)

    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())

    conn = get_connection()
    if owner_user_id is None:
        conn.execute(f"UPDATE research_tasks SET {set_clause} WHERE task_id = ?", values + [task_id])
    else:
        conn.execute(
            f"UPDATE research_tasks SET {set_clause} WHERE task_id = ? AND user_id = ?",
            values + [task_id, owner_user_id],
        )
    conn.commit()
    conn.close()
    return get_task(task_id, owner_user_id)


def list_tasks(limit: int = 20, offset: int = 0, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            "SELECT * FROM research_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM research_tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_step(
    task_id: str,
    step_index: int,
    title: str,
    description: str,
    need_search: bool = True,
    user_id: str | None = None,
) -> str:
    step_id = f"{task_id}_step_{step_index}"
    user_id = user_id or _task_user_id(task_id)
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO research_steps
           (step_id, task_id, user_id, step_index, title, description, need_search, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (step_id, task_id, user_id, step_index, title, description, 1 if need_search else 0),
    )
    conn.commit()
    conn.close()
    return step_id


def update_step(step_id: str, **kwargs) -> None:
    if "sources_json" in kwargs and isinstance(kwargs["sources_json"], list):
        kwargs["sources_json"] = json.dumps(kwargs["sources_json"], ensure_ascii=False)

    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())

    conn = get_connection()
    conn.execute(f"UPDATE research_steps SET {set_clause} WHERE step_id = ?", values + [step_id])
    conn.commit()
    conn.close()


def save_knowledge_document(
    doc_id: str,
    title: str,
    content: str,
    source_name: str = "",
    source_type: str = "text",
    status: str = "pending",
    chunk_count: int = 0,
    error_message: str = "",
    metadata: dict | None = None,
    user_id: str = LOCAL_DEFAULT_USER_ID,
) -> dict:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO knowledge_documents
           (doc_id, user_id, title, content, source_name, source_type, status, chunk_count,
            error_message, metadata_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            doc_id,
            user_id,
            title,
            content,
            source_name,
            source_type,
            status,
            chunk_count,
            error_message,
            json.dumps(metadata or {}, ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return get_knowledge_document(doc_id)


def update_knowledge_document(doc_id: str, owner_user_id: str | None = None, **kwargs) -> Optional[dict]:
    kwargs["updated_at"] = datetime.now().isoformat()
    if "metadata" in kwargs:
        kwargs["metadata_json"] = json.dumps(kwargs.pop("metadata") or {}, ensure_ascii=False)

    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())

    conn = get_connection()
    if owner_user_id is None:
        conn.execute(
            f"UPDATE knowledge_documents SET {set_clause} WHERE doc_id = ?",
            values + [doc_id],
        )
    else:
        conn.execute(
            f"UPDATE knowledge_documents SET {set_clause} WHERE doc_id = ? AND user_id = ?",
            values + [doc_id, owner_user_id],
        )
    conn.commit()
    conn.close()
    return get_knowledge_document(doc_id, owner_user_id)


def get_knowledge_document(doc_id: str, user_id: str | None = None) -> Optional[dict]:
    conn = get_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM knowledge_documents WHERE doc_id = ?", (doc_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM knowledge_documents WHERE doc_id = ? AND user_id = ?",
            (doc_id, user_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_knowledge_documents(limit: int = 50, offset: int = 0, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            """SELECT doc_id, user_id, title, source_name, source_type, length(content) AS content_length,
                  status, chunk_count, error_message, metadata_json, created_at, updated_at
           FROM knowledge_documents
           ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT doc_id, user_id, title, source_name, source_type, length(content) AS content_length,
                  status, chunk_count, error_message, metadata_json, created_at, updated_at
           FROM knowledge_documents
           WHERE user_id = ?
           ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_knowledge_document(doc_id: str, user_id: str | None = None) -> bool:
    conn = get_connection()
    if user_id is None:
        conn.execute("DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,))
        cur = conn.execute("DELETE FROM knowledge_documents WHERE doc_id = ?", (doc_id,))
    else:
        conn.execute("DELETE FROM knowledge_chunks WHERE doc_id = ? AND user_id = ?", (doc_id, user_id))
        cur = conn.execute(
            "DELETE FROM knowledge_documents WHERE doc_id = ? AND user_id = ?",
            (doc_id, user_id),
        )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def replace_knowledge_chunks(doc_id: str, chunks: list[dict], user_id: str | None = None) -> None:
    conn = get_connection()
    now = datetime.now().isoformat()
    user_id = user_id or (get_knowledge_document(doc_id) or {}).get("user_id") or LOCAL_DEFAULT_USER_ID
    conn.execute("DELETE FROM knowledge_chunks WHERE doc_id = ? AND user_id = ?", (doc_id, user_id))
    conn.executemany(
        """INSERT INTO knowledge_chunks
           (chunk_id, doc_id, user_id, chunk_index, content, page_num, source_name,
            embedding_json, metadata_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                chunk["chunk_id"],
                doc_id,
                user_id,
                chunk["chunk_index"],
                chunk["content"],
                chunk.get("page_num"),
                chunk.get("source_name") or "",
                json.dumps(chunk["embedding"], ensure_ascii=False),
                json.dumps(chunk.get("metadata") or {}, ensure_ascii=False),
                now,
            )
            for chunk in chunks
        ],
    )
    conn.commit()
    conn.close()


def list_knowledge_chunks(doc_id: str, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            """SELECT chunk_id, doc_id, user_id, chunk_index, content, page_num, source_name,
                  metadata_json, created_at
           FROM knowledge_chunks WHERE doc_id = ? ORDER BY chunk_index ASC""",
            (doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT chunk_id, doc_id, user_id, chunk_index, content, page_num, source_name,
                  metadata_json, created_at
           FROM knowledge_chunks WHERE doc_id = ? AND user_id = ? ORDER BY chunk_index ASC""",
            (doc_id, user_id),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_embedded_knowledge_chunks(user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            """SELECT c.chunk_id, c.doc_id, c.user_id, c.chunk_index, c.content, c.page_num,
                  c.source_name, c.embedding_json, c.metadata_json, d.title, d.source_type
           FROM knowledge_chunks c
           JOIN knowledge_documents d ON d.doc_id = c.doc_id
           WHERE d.status IN ('ready', 'completed')
           ORDER BY d.updated_at DESC, c.chunk_index ASC"""
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT c.chunk_id, c.doc_id, c.user_id, c.chunk_index, c.content, c.page_num,
                  c.source_name, c.embedding_json, c.metadata_json, d.title, d.source_type
           FROM knowledge_chunks c
           JOIN knowledge_documents d ON d.doc_id = c.doc_id
           WHERE d.status IN ('ready', 'completed') AND d.user_id = ?
           ORDER BY d.updated_at DESC, c.chunk_index ASC""",
            (user_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_report_version(
    task_id: str,
    content_markdown: str,
    change_note: str = "",
    user_id: str | None = None,
) -> str:
    version_id = f"ver_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    now = datetime.now().isoformat()
    user_id = user_id or _task_user_id(task_id)
    conn = get_connection()
    conn.execute(
        """INSERT INTO report_versions
           (version_id, task_id, user_id, content_markdown, change_note, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (version_id, task_id, user_id, content_markdown, change_note, now),
    )
    conn.commit()
    conn.close()
    return version_id


def list_report_versions(task_id: str, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            """SELECT version_id, task_id, user_id, change_note, created_at, length(content_markdown) AS content_length
           FROM report_versions WHERE task_id = ? ORDER BY created_at DESC""",
            (task_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT version_id, task_id, user_id, change_note, created_at, length(content_markdown) AS content_length
           FROM report_versions WHERE task_id = ? AND user_id = ? ORDER BY created_at DESC""",
            (task_id, user_id),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report_version(version_id: str, user_id: str | None = None) -> Optional[dict]:
    conn = get_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM report_versions WHERE version_id = ?", (version_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM report_versions WHERE version_id = ? AND user_id = ?",
            (version_id, user_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_artifact(
    artifact_id: str,
    task_id: str,
    artifact_type: str,
    title: str,
    content: str,
    metadata: dict | None = None,
    user_id: str | None = None,
) -> dict:
    now = datetime.now().isoformat()
    user_id = user_id or _task_user_id(task_id)
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO artifacts
           (artifact_id, task_id, user_id, artifact_type, title, content, metadata_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            artifact_id,
            task_id,
            user_id,
            artifact_type,
            title,
            content,
            json.dumps(metadata or {}, ensure_ascii=False),
            now,
        ),
    )
    conn.commit()
    conn.close()
    return get_artifact(artifact_id)


def get_artifact(artifact_id: str, user_id: str | None = None) -> Optional[dict]:
    conn = get_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ? AND user_id = ?",
            (artifact_id, user_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_artifacts(task_id: str, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            """SELECT artifact_id, task_id, user_id, artifact_type, title, metadata_json, created_at
           FROM artifacts WHERE task_id = ? ORDER BY created_at DESC""",
            (task_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT artifact_id, task_id, user_id, artifact_type, title, metadata_json, created_at
           FROM artifacts WHERE task_id = ? AND user_id = ? ORDER BY created_at DESC""",
            (task_id, user_id),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Agent Trace
# ============================================================

def save_agent_run(
    task_id: str,
    agent_name: str,
    phase: str,
    status: str,
    input_summary: str = "",
    output_summary: str = "",
    tool_calls: list[dict] | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    elapsed_seconds: float = 0.0,
    error: str = "",
    user_id: str | None = None,
) -> dict:
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    now = datetime.now().isoformat()
    user_id = user_id or _task_user_id(task_id)
    conn = get_connection()
    conn.execute(
        """INSERT INTO agent_runs
           (run_id, task_id, user_id, agent_name, phase, status, input_summary, output_summary,
            tool_calls_json, prompt_tokens, completion_tokens, elapsed_seconds, error, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            task_id,
            user_id,
            agent_name,
            phase,
            status,
            input_summary[:2000],
            output_summary[:4000],
            json.dumps(tool_calls or [], ensure_ascii=False),
            prompt_tokens,
            completion_tokens,
            elapsed_seconds,
            error[:2000],
            now,
        ),
    )
    conn.commit()
    conn.close()
    return get_agent_run(run_id)


def get_agent_run(run_id: str, user_id: str | None = None) -> Optional[dict]:
    conn = get_connection()
    if user_id is None:
        row = conn.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM agent_runs WHERE run_id = ? AND user_id = ?",
            (run_id, user_id),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_agent_runs(task_id: str, user_id: str | None = None) -> list[dict]:
    conn = get_connection()
    if user_id is None:
        rows = conn.execute(
            "SELECT * FROM agent_runs WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agent_runs WHERE task_id = ? AND user_id = ? ORDER BY created_at ASC",
            (task_id, user_id),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
