#!/usr/bin/env python3
"""
DeepFlow CLI — 命令行深度研究工具

用法:
    python -m cli.main "分析 2026 年 AI Agent 市场发展趋势"
    python -m cli.main "什么是量子计算" --locale en-US --max-steps 3
    python -m cli.main --interactive  # 交互模式
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Windows GBK 编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from cli.config import Config
from cli.models import ResearchPlan, ResearchStep
from cli.state_machine import ResearchStateMachine

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("deepflow")

console = Console(force_terminal=True, legacy_windows=False)

# ============================================================
# CLI 入口
# ============================================================


async def main():
    parser = argparse.ArgumentParser(
        description="DeepFlow - AI 深度研究 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m cli.main "分析 2026 年 AI Agent 市场趋势"
  python -m cli.main "量子计算最新进展" --max-steps 3
  python -m cli.main "什么是机器学习" --locale en-US
  python -m cli.main --interactive
        """,
    )
    parser.add_argument("topic", nargs="?", help="研究主题")
    parser.add_argument("--locale", default="zh-CN", help="语言 (zh-CN | en-US)")
    parser.add_argument("--max-steps", type=int, default=None, help="最大研究步骤数")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    parser.add_argument("--no-confirm", "-y", action="store_true", help="跳过计划确认，直接执行")
    parser.add_argument("--debug", action="store_true", help="调试模式")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # 校验配置
    missing = Config.validate()
    if missing:
        console.print("[red]配置缺失:[/red]")
        for m in missing:
            console.print(f"  - {m}")
        console.print("\n请复制 .env.example 为 .env 并填入你的 API Key")
        return 1

    # 覆盖配置
    if args.max_steps:
        Config.MAX_STEPS = args.max_steps

    # 交互模式
    if args.interactive:
        return await interactive_mode(args)

    # 单次研究模式
    topic = args.topic
    if not topic:
        console.print("[red]请提供研究主题[/red]")
        console.print("用法: python -m cli.main \"你的研究主题\"")
        console.print("或:  python -m cli.main --interactive")
        return 1

    return await single_research(topic, args.locale, args.no_confirm)


# ============================================================
# 单次研究
# ============================================================


async def single_research(topic: str, locale: str, skip_confirm: bool = False) -> int:
    """执行单次研究"""

    # 显示配置
    console.print(Panel.fit(
        f"[bold cyan]DeepFlow[/bold cyan] - AI 深度研究\n\n"
        f"[dim]研究主题: {topic}\n"
        f"语言: {locale}\n"
        f"最大步骤: {Config.MAX_STEPS}\n"
        f"模型: Planner={Config.PLANNER_MODEL} | Researcher={Config.RESEARCHER_MODEL} | Reporter={Config.REPORTER_MODEL}[/dim]",
        title="🚀 启动",
    ))

    # 创建状态机
    sm = ResearchStateMachine(topic=topic, locale=locale)

    # 设置进度回调
    async def on_progress(event: str, message: str):
        icons = {
            "planning": "📋",
            "plan_created": "📋",
            "research_started": "🔍",
            "step_started": "  →",
            "step_completed": "  ✅",
            "report_started": "📝",
            "completed": "✨",
            "error": "❌",
        }
        icon = icons.get(event, "•")
        if event in ("step_started", "step_completed"):
            console.print(f"{icon} {message}")
        elif event == "step_started":
            pass  # 不重复打印
        else:
            console.print(f"\n{icon} [bold]{message}[/bold]")

    sm.on_progress = on_progress

    # 设置计划确认回调（除非 --no-confirm）
    if not skip_confirm:

        async def on_plan_ready(plan: ResearchPlan) -> str:
            """显示计划并等待用户确认"""
            console.print()
            display_plan(plan)
            console.print()

            while True:
                choice = console.input(
                    "[bold]确认此计划？[/bold] "
                    "[[green]y[/green]=确认 / [yellow]e[/yellow]=编辑 / [red]n[/red]=取消]: "
                ).strip().lower()

                if choice in ("y", "yes", ""):
                    return "accept"
                elif choice in ("e", "edit"):
                    console.print("[yellow]编辑功能暂未实现，将直接接受计划[/yellow]")
                    return "accept"
                elif choice in ("n", "no"):
                    return "reject"
                else:
                    console.print("[red]无效选择[/red]")

        sm.on_plan_ready = on_plan_ready

    # 执行
    console.print("\n[dim]开始研究...[/dim]\n")
    record = await sm.run()

    # 保存结果
    save_results(record)

    # 显示结果
    display_results(record)

    return 0 if record.status == "completed" else 1


# ============================================================
# 交互模式
# ============================================================


async def interactive_mode(args) -> int:
    """交互式 CLI"""
    console.print(Panel.fit(
        "[bold cyan]DeepFlow[/bold cyan] - 交互模式\n\n"
        "输入研究主题开始，输入 [yellow]:q[/yellow] 退出\n"
        "输入 [yellow]:config[/yellow] 查看配置",
        title="🤖",
    ))

    while True:
        console.print()
        try:
            topic = console.input("[bold cyan]研究主题[/bold cyan]: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]再见！[/dim]")
            break

        if not topic:
            continue
        if topic == ":q":
            console.print("[dim]再见！[/dim]")
            break
        if topic == ":config":
            console.print(Config.display())
            continue

        await single_research(topic, args.locale, args.no_confirm)

    return 0


# ============================================================
# 显示和保存
# ============================================================


def display_plan(plan: ResearchPlan):
    """显示研究计划"""
    table = Table(title=f"📋 研究计划: {plan.title}", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("类型", width=6)
    table.add_column("步骤", min_width=40)
    table.add_column("描述", min_width=30)

    for i, step in enumerate(plan.steps, 1):
        icon = "🔍 搜索" if step.need_search else "💻 处理"
        table.add_row(str(i), icon, step.title, step.description[:80] + ("..." if len(step.description) > 80 else ""))

    console.print(table)

    if plan.thought:
        console.print(f"\n[dim]AI 思考: {plan.thought}[/dim]")


def display_results(record):
    """显示研究结果摘要"""
    console.print()

    if record.status == "completed":
        console.print(f"\n[bold green]✅ 研究完成！[/bold green]")

        # 统计表
        stats = Table(title="📊 统计", show_header=False)
        stats.add_column(style="dim")
        stats.add_column()
        stats.add_row("研究步骤", f"{len(record.findings)} 个")
        stats.add_row("引用来源", f"{sum(len(f.references) for f in record.findings)} 个")
        stats.add_row("Token 用量", f"{record.usage.total_tokens:,}")
        stats.add_row("预估费用", f"¥{record.usage.cost_estimate_rmb:.4f}")
        stats.add_row("耗时", f"{record.usage.elapsed_seconds:.1f} 秒")
        stats.add_row("输出文件", f"output/{record.run_id}/report.md")
        console.print(stats)

        # 显示报告预览
        console.print("\n[bold]报告预览:[/bold]\n")
        preview = record.report_markdown[:2000]
        if len(record.report_markdown) > 2000:
            preview += "\n\n... (完整报告见输出文件)"
        console.print(Markdown(preview))
    else:
        console.print(f"\n[bold red]❌ 研究失败[/bold red]")
        for err in record.errors:
            console.print(f"  [red]- {err}[/red]")


def save_results(record):
    """保存研究结果到 output 目录"""
    run_dir = Config.OUTPUT_DIR / record.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 保存完整记录 (JSON)
    record_path = run_dir / "record.json"
    record_path.write_text(
        record.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 保存报告 (Markdown)
    report_path = run_dir / "report.md"
    report_path.write_text(record.report_markdown, encoding="utf-8")

    # 保存日志
    log_path = run_dir / "summary.txt"
    log_text = f"""DeepFlow 研究记录
================
运行 ID: {record.run_id}
主题: {record.topic}
状态: {record.status}
时间: {datetime.now().isoformat()}

研究计划:
{record.plan.model_dump_json(indent=2, ensure_ascii=False) if record.plan else 'N/A'}

统计:
- 步骤数: {len(record.findings)}
- 引用数: {sum(len(f.references) for f in record.findings)}
- Token: {record.usage.total_tokens:,}
- 费用: ¥{record.usage.cost_estimate_rmb:.4f}
- 耗时: {record.usage.elapsed_seconds:.1f}s

错误:
{chr(10).join(f'- {e}' for e in record.errors) if record.errors else '无'}
"""
    log_path.write_text(log_text, encoding="utf-8")

    console.print(f"\n[dim]结果已保存到: {run_dir}[/dim]")


# ============================================================
# Entry Point
# ============================================================


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
