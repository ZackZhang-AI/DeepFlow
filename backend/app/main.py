"""
DeepFlow Backend — FastAPI 应用入口

启动:
    cd backend && uvicorn app.main:app --reload
    python -m backend.app.main  (直接运行)
"""

import sys
import os
from pathlib import Path

# 确保项目根目录在 path 中
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager

from backend.app.config import CORS_ORIGINS
from backend.app.core.auth import cleanup_expired_sessions, ensure_demo_user
from backend.app.core.db import get_db_path, init_db
from backend.app.core.job_queue import start_job_worker, stop_job_worker
from backend.app.services.job_handlers import register_handlers
from backend.app.core.logging_config import configure_logging
from backend.app.core.errors import http_error_payload
from backend.app.api.routes import (
    artifacts,
    auth,
    events,
    knowledge,
    report,
    research,
    system,
    templates,
    tools,
    workflows,
    workspaces,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    configure_logging()
    init_db()
    ensure_demo_user()
    cleanup_expired_sessions()
    register_handlers()
    await start_job_worker()
    print(f"Database initialized at: {get_db_path()}")
    yield
    await stop_job_worker()


app = FastAPI(
    title="DeepFlow API",
    description="AI 深度研究平台 — 后端 API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(http_error_payload(exc)),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    detail = exc.errors()
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {
                "error_code": "validation_error",
                "message": "Request validation failed",
                "detail": detail,
                "details": detail,
            }
        ),
    )

# CORS — 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(research.router)
app.include_router(system.router)
app.include_router(events.router)
app.include_router(report.router)
app.include_router(artifacts.router)
app.include_router(knowledge.router)
app.include_router(auth.router)
app.include_router(tools.router)
app.include_router(workspaces.router)
app.include_router(workspaces.share_router)
app.include_router(workspaces.public_router)
app.include_router(templates.router)
app.include_router(workflows.router)


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "version": "0.1.0"}


# ============================================================
# 直接运行入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
