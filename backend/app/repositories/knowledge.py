"""Knowledge document and chunk persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from backend.app.core.db import LOCAL_DEFAULT_USER_ID, get_connection

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
    workspace_id: str | None = None,
    project_id: str | None = None,
) -> dict:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO knowledge_documents
           (doc_id, user_id, title, content, source_name, source_type, status, chunk_count,
            error_message, metadata_json, workspace_id, project_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            workspace_id,
            project_id,
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
                  status, chunk_count, error_message, metadata_json, workspace_id, project_id,
                  created_at, updated_at
               FROM knowledge_documents d
               WHERE d.user_id = ?
                  OR EXISTS (
                      SELECT 1 FROM workspace_members m
                      WHERE m.workspace_id = d.workspace_id AND m.user_id = ?
                  )
               ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
            (user_id, user_id, limit, offset),
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
           WHERE d.status IN ('ready', 'completed')
             AND (
               d.user_id = ?
               OR EXISTS (
                 SELECT 1 FROM workspace_members m
                 WHERE m.workspace_id = d.workspace_id AND m.user_id = ?
               )
             )
           ORDER BY d.updated_at DESC, c.chunk_index ASC""",
            (user_id, user_id),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
