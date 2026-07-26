"""User and session persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from backend.app.core.db import get_connection

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


def delete_auth_session(token_hash: str) -> bool:
    conn = get_connection()
    cursor = conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def delete_expired_auth_sessions(now: str) -> int:
    conn = get_connection()
    cursor = conn.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))
    conn.commit()
    conn.close()
    return cursor.rowcount
