"""Per-user tool setting persistence."""

from __future__ import annotations

from datetime import datetime

from backend.app.core.db import get_connection

def get_tool_setting(user_id: str, tool_id: str) -> bool | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT enabled FROM user_tool_settings WHERE user_id = ? AND tool_id = ?",
        (user_id, tool_id),
    ).fetchone()
    conn.close()
    return bool(row["enabled"]) if row else None


def set_tool_setting(user_id: str, tool_id: str, enabled: bool) -> None:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO user_tool_settings (user_id, tool_id, enabled, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(user_id, tool_id) DO UPDATE SET
             enabled = excluded.enabled, updated_at = excluded.updated_at""",
        (user_id, tool_id, 1 if enabled else 0, now),
    )
    conn.commit()
    conn.close()
