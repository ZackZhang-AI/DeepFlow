"""
报告 API — 获取、导出、重写
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from io import BytesIO
import re
from urllib.parse import quote

from fastapi.responses import PlainTextResponse, StreamingResponse

from backend.app.models.schemas import ReportResponse, RewriteRequest, SaveReportRequest
from backend.app.core.auth import require_login
from backend.app.core.rate_limit import check_rate_limit
from backend.app.core.runtime_config import artifact_rate_limit
from backend.app.core.db import (
    get_report_version,
    get_task,
    list_report_versions,
    save_report_version,
    update_task,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{task_id}", response_model=ReportResponse)
async def get_report(task_id: str, user: dict = Depends(require_login)):
    """获取研究报告"""
    task = get_task(task_id, user_id=user["user_id"])
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


@router.patch("/{task_id}")
async def save_report(task_id: str, req: SaveReportRequest, user: dict = Depends(require_login)):
    """保存报告编辑，并记录版本"""
    task = get_task(task_id, user_id=user["user_id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.get("report_markdown"):
        raise HTTPException(status_code=404, detail="报告尚未生成")

    version_id = save_report_version(
        task_id=task_id,
        content_markdown=task["report_markdown"],
        change_note=req.change_note,
        user_id=user["user_id"],
    )
    update_task(task_id, owner_user_id=user["user_id"], report_markdown=req.content_markdown)
    return {"status": "saved", "task_id": task_id, "previous_version_id": version_id}


@router.get("/{task_id}/versions")
async def versions(task_id: str, user: dict = Depends(require_login)):
    """列出报告版本"""
    if get_task(task_id, user_id=user["user_id"]) is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return list_report_versions(task_id, user_id=user["user_id"])


@router.get("/versions/{version_id}")
async def version_detail(version_id: str, user: dict = Depends(require_login)):
    """获取某个报告版本正文"""
    version = get_report_version(version_id, user_id=user["user_id"])
    if version is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    return version


@router.post("/{task_id}/versions/{version_id}/restore")
async def restore_report_version(task_id: str, version_id: str, user: dict = Depends(require_login)):
    """恢复某个报告版本，并先备份当前报告。"""
    task = get_task(task_id, user_id=user["user_id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    current = task.get("report_markdown") or ""
    if not current:
        raise HTTPException(status_code=404, detail="报告尚未生成")

    version = get_report_version(version_id, user_id=user["user_id"])
    if version is None or version.get("task_id") != task_id:
        raise HTTPException(status_code=404, detail="版本不存在")

    backup_version_id = save_report_version(
        task_id=task_id,
        content_markdown=current,
        change_note=f"恢复版本 {version_id} 前自动备份",
        user_id=user["user_id"],
    )
    update_task(
        task_id,
        owner_user_id=user["user_id"],
        report_markdown=version["content_markdown"],
    )
    return {
        "status": "restored",
        "task_id": task_id,
        "restored_version_id": version_id,
        "backup_version_id": backup_version_id,
        "report_markdown": version["content_markdown"],
    }


@router.get("/{task_id}/download")
async def download_report(task_id: str, format: str = Query("markdown", pattern="^(markdown|md|pdf)$"), user: dict = Depends(require_login)):
    """下载报告文件"""
    task = get_task(task_id, user_id=user["user_id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task["report_markdown"]:
        raise HTTPException(status_code=404, detail="报告尚未生成")

    # 生成文件名
    safe_topic = _safe_filename(task["topic"])[:50]
    normalized_format = "markdown" if format == "md" else format

    if normalized_format == "pdf":
        pdf = _render_report_pdf(task["report_markdown"], task["topic"])
        filename = f"DeepFlow_{safe_topic}.pdf"
        return StreamingResponse(
            BytesIO(pdf),
            media_type="application/pdf",
            headers={"Content-Disposition": _attachment_header(filename)},
        )

    filename = f"DeepFlow_{safe_topic}.md"

    return PlainTextResponse(
        content=task["report_markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": _attachment_header(filename)},
    )


@router.post("/{task_id}/rewrite")
async def rewrite_report_section(task_id: str, req: RewriteRequest, user: dict = Depends(require_login)):
    check_rate_limit("artifacts.generate", user["user_id"], artifact_rate_limit())
    """按用户指令重写报告或某个章节，并保存版本"""
    task = get_task(task_id, user_id=user["user_id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    current = task.get("report_markdown") or ""
    if not current:
        raise HTTPException(status_code=404, detail="报告尚未生成")

    from cli.agents.base import LLMProvider
    from cli.config import Config

    section_hint = req.section.strip() or "整篇报告"
    system_prompt = """你是 DeepFlow 的报告编辑 Agent。你只能基于用户提供的原报告进行改写。
要求：
- 保留事实、引用链接和重要数据，不要编造新事实
- 按用户指令改写指定章节或整篇报告
- 输出完整 Markdown 报告，而不是只输出片段
- 如果用户要求无法满足，在报告中保留原内容并说明限制"""
    user_message = f"""## 要改写的范围
{section_hint}

## 改写指令
{req.instruction}

## 当前报告
{current}

请输出改写后的完整 Markdown 报告。"""

    rewritten, pt, ct = await LLMProvider.generate_text(
        model=Config.REPORTER_MODEL,
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.25,
        max_tokens=8192,
    )

    version_id = save_report_version(
        task_id=task_id,
        content_markdown=current,
        change_note=f"AI rewrite: {req.instruction[:80]}",
        user_id=user["user_id"],
    )
    update_task(
        task_id,
        owner_user_id=user["user_id"],
        report_markdown=rewritten,
        tokens_used=(task.get("tokens_used") or 0) + pt + ct,
    )
    return {
        "status": "rewritten",
        "task_id": task_id,
        "previous_version_id": version_id,
        "report_markdown": rewritten,
        "tokens": pt + ct,
    }


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n]+', "_", value).strip("._ ")
    return cleaned or "report"


def _attachment_header(filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "download"
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'


def _render_report_pdf(markdown: str, fallback_title: str) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            ListFlowable,
            ListItem,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="PDF 导出需要 reportlab，请先安装 requirements.txt 中的依赖。",
        ) from exc

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    base_font = "STSong-Light"

    styles.add(ParagraphStyle(
        name="DeepFlowTitle",
        parent=styles["Title"],
        fontName=base_font,
        fontSize=20,
        leading=28,
        spaceAfter=12,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name="DeepFlowHeading2",
        parent=styles["Heading2"],
        fontName=base_font,
        fontSize=15,
        leading=22,
        spaceBefore=12,
        spaceAfter=7,
        textColor=colors.HexColor("#164e63"),
    ))
    styles.add(ParagraphStyle(
        name="DeepFlowHeading3",
        parent=styles["Heading3"],
        fontName=base_font,
        fontSize=12,
        leading=18,
        spaceBefore=8,
        spaceAfter=5,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name="DeepFlowBody",
        parent=styles["BodyText"],
        fontName=base_font,
        fontSize=10,
        leading=16,
        spaceAfter=6,
        wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="DeepFlowCode",
        parent=styles["Code"],
        fontName=base_font,
        fontSize=8,
        leading=12,
        backColor=colors.HexColor("#f8fafc"),
        borderColor=colors.HexColor("#e2e8f0"),
        borderWidth=0.5,
        borderPadding=5,
        wordWrap="CJK",
    ))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=fallback_title,
    )

    story = []
    bullet_items = []
    code_lines: list[str] = []
    in_code = False

    def flush_bullets() -> None:
        nonlocal bullet_items
        if bullet_items:
            story.append(ListFlowable(
                [ListItem(Paragraph(item, styles["DeepFlowBody"])) for item in bullet_items],
                bulletType="bullet",
                leftIndent=14,
            ))
            bullet_items = []

    def flush_code() -> None:
        nonlocal code_lines
        if code_lines:
            story.append(Paragraph("<br/>".join(_inline_markup(line) for line in code_lines), styles["DeepFlowCode"]))
            story.append(Spacer(1, 4))
            code_lines = []

    title_written = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_bullets()
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            flush_bullets()
            story.append(Spacer(1, 4))
            continue
        if re.fullmatch(r"[-*_]{3,}", stripped):
            flush_bullets()
            story.append(Table([[""]], colWidths=[doc.width], style=TableStyle([
                ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ])))
            story.append(Spacer(1, 8))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_bullets()
            level = len(heading.group(1))
            text = _inline_markup(heading.group(2))
            if level == 1 and not title_written:
                story.append(Paragraph(text, styles["DeepFlowTitle"]))
                title_written = True
            elif level <= 2:
                story.append(Paragraph(text, styles["DeepFlowHeading2"]))
            else:
                story.append(Paragraph(text, styles["DeepFlowHeading3"]))
            continue

        bullet = re.match(r"^[-*+]\s+(.+)$", stripped)
        if bullet:
            bullet_items.append(_inline_markup(bullet.group(1)))
            continue

        flush_bullets()
        story.append(Paragraph(_inline_markup(stripped), styles["DeepFlowBody"]))

    flush_bullets()
    flush_code()
    if not story:
        story.append(Paragraph(_inline_markup(fallback_title), styles["DeepFlowTitle"]))
    doc.build(story)
    return buffer.getvalue()


def _inline_markup(text: str) -> str:
    from xml.sax.saxutils import escape

    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"[*_`]+", "", text)
    return escape(text)
