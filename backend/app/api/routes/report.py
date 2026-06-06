"""
报告 API — 获取、导出、重写
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from backend.app.models.schemas import ReportResponse
from backend.app.core.db import get_task

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{task_id}", response_model=ReportResponse)
async def get_report(task_id: str):
    """获取研究报告"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="研究尚未完成")
    if not task["report_markdown"]:
        raise HTTPException(status_code=404, detail="报告尚未生成")

    title = "研究报告"
    if task["report_markdown"]:
        lines = task["report_markdown"].split("\n")
        for line in lines:
            if line.startswith("# ") and not line.startswith("## "):
                title = line[2:].strip()
                break

    return ReportResponse(
        report_id=f"rep_{task_id}",
        task_id=task_id,
        title=title,
        content_markdown=task["report_markdown"],
        sources_count=task["sources_count"] or 0,
        tokens_used=task["tokens_used"] or 0,
        cost_rmb=task["cost_rmb"] or 0.0,
        elapsed_seconds=task["elapsed_seconds"] or 0.0,
        created_at=task["created_at"],
    )


@router.get("/{task_id}/download")
async def download_report(task_id: str, format: str = Query("markdown", regex="^(markdown|md)$")):
    """下载报告文件"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task["report_markdown"]:
        raise HTTPException(status_code=404, detail="报告尚未生成")

    # 生成文件名
    safe_topic = task["topic"].replace(" ", "_")[:50]
    filename = f"DeepFlow_{safe_topic}.md"

    return PlainTextResponse(
        content=task["report_markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{task_id}/rewrite")
async def rewrite_report_section(task_id: str):
    """报告局部重写 — Phase 3"""
    return {"status": "not_implemented", "task_id": task_id}
