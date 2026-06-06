"""
Backend 配置 — 复用 CLI 的 Config 并扩展
"""

import os
from pathlib import Path

# 项目根目录 (backend/../)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

# ---- 数据库 ----
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BACKEND_DIR}/deepflow.db")

# ---- 服务 ----
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# ---- 研究任务 ----
RESEARCH_TIMEOUT_MINUTES = int(os.getenv("RESEARCH_TIMEOUT_MINUTES", "30"))

# ---- 复用 CLI 配置 ----
# 将项目根目录加入 path，以便导入 cli 模块
import sys
sys.path.insert(0, str(ROOT_DIR))

from cli.config import Config as CLIConfig

Config = CLIConfig  # 复用
