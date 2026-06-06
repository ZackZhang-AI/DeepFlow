"""
Artifact 生成 API — 播客脚本、PPT、文本操作
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.db import get_task

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

logger = logging.getLogger("deepflow.artifacts")


class ArtifactRequest(BaseModel):
    task_id: str = Field(..., description="研究任务 ID")
    locale: str = Field(default="zh-CN")
    style: str = Field(default="general")  # for report re-generation


class ProsRequest(BaseModel):
    text: str = Field(..., min_length=10, description="待处理的文本")
    instruction: str = Field(default="")


# ============================================================
# 播客脚本
# ============================================================

@router.post("/podcast")
async def generate_podcast(req: ArtifactRequest):
    """将报告转化为播客脚本"""
    task = get_task(req.task_id)
    if not task or not task.get("report_markdown"):
        raise HTTPException(status_code=404, detail="报告不存在")

    import sys
    from pathlib import Path
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
    sys.path.insert(0, str(ROOT_DIR))

    from cli.agents.artifacts.podcast import generate_podcast_script, format_script_for_display

    title = task.get("plan_json", "")
    try:
        import json
        plan = json.loads(title) if title else {}
        title = plan.get("title", task["topic"])
    except Exception:
        title = task["topic"]

    script, pt, ct = await generate_podcast_script(
        report_markdown=task["report_markdown"],
        report_title=title,
        locale=req.locale,
    )

    if script is None:
        raise HTTPException(status_code=500, detail="播客脚本生成失败")

    return {
        "script": script.model_dump(),
        "display": format_script_for_display(script),
        "tokens": pt + ct,
    }


# ============================================================
# PPT
# ============================================================

@router.post("/ppt")
async def generate_ppt(req: ArtifactRequest):
    """将报告转化为 PPT Markdown"""
    task = get_task(req.task_id)
    if not task or not task.get("report_markdown"):
        raise HTTPException(status_code=404, detail="报告不存在")

    import sys
    from pathlib import Path
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
    sys.path.insert(0, str(ROOT_DIR))

    from cli.agents.artifacts.ppt import compose_ppt

    title = task["topic"]
    try:
        import json
        plan = json.loads(task.get("plan_json", "{}"))
        title = plan.get("title", task["topic"])
    except Exception:
        pass

    slides, pt, ct = await compose_ppt(
        report_markdown=task["report_markdown"],
        report_title=title,
        locale=req.locale,
    )

    return {
        "slides_markdown": slides,
        "slides_count": slides.count("---") + 1,
        "tokens": pt + ct,
    }


# ============================================================
# 文本润色
# ============================================================

@router.post("/prose/improve")
async def improve_prose(req: ProsRequest):
    """润色文本"""
    import sys
    from pathlib import Path
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
    sys.path.insert(0, str(ROOT_DIR))

    from cli.agents.artifacts.prose import improve_text

    result, pt, ct = await improve_text(req.text, req.instruction)
    return {"result": result, "tokens": pt + ct}


@router.post("/prose/expand")
async def expand_prose(req: ProsRequest):
    """扩展文本"""
    import sys
    from pathlib import Path
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
    sys.path.insert(0, str(ROOT_DIR))

    from cli.agents.artifacts.prose import expand_text

    result, pt, ct = await expand_text(req.text)
    return {"result": result, "tokens": pt + ct}


@router.post("/prose/shorten")
async def shorten_prose(req: ProsRequest):
    """精简文本"""
    import sys
    from pathlib import Path
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
    sys.path.insert(0, str(ROOT_DIR))

    from cli.agents.artifacts.prose import shorten_text

    result, pt, ct = await shorten_text(req.text)
    return {"result": result, "tokens": pt + ct}


# ============================================================
# 多风格重生成
# ============================================================

@router.post("/restyle")
async def restyle_report(req: ArtifactRequest):
    """用指定风格重新生成报告"""
    task = get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    import sys
    from pathlib import Path
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
    sys.path.insert(0, str(ROOT_DIR))

    from cli.agents.reporter import generate_report
    from cli.models import ResearchPlan, ResearchFinding

    # 重建 plan
    plan = ResearchPlan(title=task["topic"], locale=req.locale, has_enough_context=True, thought="", steps=[])
    try:
        import json
        pd = json.loads(task.get("plan_json", "{}"))
        plan = ResearchPlan(**pd)
    except Exception:
        pass

    # 简化版：直接复用缓存报告内容作为 findings 输入
    findings: list = []
    if task.get("report_markdown"):
        findings = [
            ResearchFinding(
                step_id="restyle_1",
                step_title="研究内容",
                problem_statement=task["topic"],
                findings_markdown=task["report_markdown"],
                conclusion="",
                references=[],
            )
        ]

    report, pt, ct = await generate_report(
        plan=plan,
        findings=findings,
        locale=req.locale,
        report_style=req.style,
    )

    return {
        "style": req.style,
        "report_markdown": report,
        "tokens": pt + ct,
    }
