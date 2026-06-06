"""
SQLite 数据库 — MVP 阶段轻量持久化
使用 WAL 模式，单进程单线程无需锁
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.app.config import BACKEND_DIR

DB_PATH = BACKEND_DIR / "deepflow.db"


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS research_tasks (
            task_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            locale TEXT DEFAULT 'zh-CN',
            status TEXT DEFAULT 'init',
            plan_json TEXT,
            report_markdown TEXT,
            current_step INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 0,
            sources_count INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            cost_rmb REAL DEFAULT 0.0,
            elapsed_seconds REAL DEFAULT 0.0,
            errors_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS research_steps (
            step_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
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
    """)
    conn.commit()
    conn.close()


# ============================================================
# 任务 CRUD
# ============================================================

def create_task(task_id: str, topic: str, locale: str = "zh-CN") -> dict:
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO research_tasks (task_id, topic, locale, status, created_at, updated_at)
           VALUES (?, ?, ?, 'coordinating', ?, ?)""",
        (task_id, topic, locale, now, now),
    )
    conn.commit()
    conn.close()
    return get_task(task_id)


def get_task(task_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM research_tasks WHERE task_id = ?", (task_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def update_task(task_id: str, **kwargs) -> Optional[dict]:
    """更新任务字段"""
    kwargs["updated_at"] = datetime.now().isoformat()
    if "errors_json" in kwargs and isinstance(kwargs["errors_json"], list):
        kwargs["errors_json"] = json.dumps(kwargs["errors_json"], ensure_ascii=False)

    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())

    conn = get_connection()
    conn.execute(
        f"UPDATE research_tasks SET {set_clause} WHERE task_id = ?",
        values + [task_id],
    )
    conn.commit()
    conn.close()
    return get_task(task_id)


def list_tasks(limit: int = 20, offset: int = 0) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM research_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# 步骤 CRUD
# ============================================================

def save_step(task_id: str, step_index: int, title: str, description: str,
              need_search: bool = True) -> str:
    step_id = f"{task_id}_step_{step_index}"
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO research_steps
           (step_id, task_id, step_index, title, description, need_search, status)
           VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
        (step_id, task_id, step_index, title, description, 1 if need_search else 0),
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
    conn.execute(
        f"UPDATE research_steps SET {set_clause} WHERE step_id = ?",
        values + [step_id],
    )
    conn.commit()
    conn.close()
