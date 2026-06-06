#!/usr/bin/env python3
"""
DeepFlow Eval Runner — Agent 评测执行器

用法:
    python -m evals.runner --agent planner
    python -m evals.runner --agent researcher --case all
    python -m evals.runner --agent all
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Windows GBK 编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cli.config import Config
from cli.models import ResearchPlan, ResearchFinding
from cli.agents.planner import generate_plan

console = Console(force_terminal=True, legacy_windows=False)


def load_cases(agent_name: str) -> list[dict]:
    """加载 eval cases"""
    case_path = Config.EVALS_DIR / "cases" / f"{agent_name}.yaml"
    if not case_path.exists():
        console.print(f"[red]Eval case 文件不存在: {case_path}[/red]")
        return []

    with open(case_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("cases", [])


async def eval_planner(cases: list[dict]) -> list[dict]:
    """评测 Planner"""
    results = []

    for i, case in enumerate(cases, 1):
        input_topic = case["input"]
        expected = case.get("expected", {})

        console.print(f"\n[bold]Case {i}/{len(cases)}: {input_topic}[/bold]")

        start = time.time()
        plan, pt, ct = await generate_plan(
            topic=input_topic,
            max_steps=Config.MAX_STEPS,
        )
        elapsed = time.time() - start

        # 评测维度
        checks = {}

        # 1. 步骤数在范围内
        min_steps = expected.get("min_steps", 2)
        max_steps = expected.get("max_steps", 5)
        checks["步骤数量"] = min_steps <= len(plan.steps) <= max_steps

        # 2. has_enough_context
        if "has_enough_context" in expected:
            checks["上下文判断"] = plan.has_enough_context == expected["has_enough_context"]

        # 3. 包含关键维度
        if "should_cover" in expected:
            all_text = " ".join(s.title + s.description for s in plan.steps)
            covered = []
            for keyword in expected["should_cover"]:
                is_covered = keyword.lower() in all_text.lower()
                covered.append(is_covered)
            checks["维度覆盖"] = all(covered)
            if not all(covered):
                missing = [expected["should_cover"][j] for j, c in enumerate(covered) if not c]
                checks["维度覆盖_detail"] = f"缺失: {missing}"

        # 4. 所有步骤都有 need_search
        if "all_need_search" in expected and expected["all_need_search"]:
            checks["搜索标记"] = all(s.need_search for s in plan.steps)

        # 5. JSON 合法性 (由 pydantic 保证，这里只记录)
        checks["JSON合法"] = True

        # 6. title 不为空
        checks["标题非空"] = bool(plan.title)

        passed = all(
            v if isinstance(v, bool) else True
            for k, v in checks.items()
            if not k.endswith("_detail")
        )

        results.append({
            "case": i,
            "input": input_topic,
            "passed": passed,
            "checks": checks,
            "plan_steps": len(plan.steps),
            "plan_title": plan.title,
            "tokens": pt + ct,
            "elapsed": f"{elapsed:.1f}s",
        })

        icon = "✅" if passed else "❌"
        console.print(f"  {icon} {'通过' if passed else '未通过'} | 步骤: {len(plan.steps)} | Token: {pt+ct} | 耗时: {elapsed:.1f}s")
        if not passed:
            for check_name, check_result in checks.items():
                if isinstance(check_result, bool) and not check_result:
                    console.print(f"    [red]✗ {check_name}[/red]")
                elif isinstance(check_result, str):
                    console.print(f"    [yellow]  {check_result}[/yellow]")

    return results


async def eval_all(agents: list[str] | None = None):
    """运行所有 Agent 评测"""
    if agents is None:
        agents = ["planner"]

    all_results = {}

    for agent in agents:
        console.print(Panel(f"[bold]评测 {agent.upper()} Agent[/bold]"))

        cases = load_cases(agent)
        if not cases:
            console.print("[yellow]无 eval cases[/yellow]")
            continue

        if agent == "planner":
            results = await eval_planner(cases)
            all_results[agent] = results

        # 显示汇总
        passed = sum(1 for r in results if r["passed"])
        console.print(f"\n[bold]{agent} 评测结果: {passed}/{len(results)} 通过[/bold]")

    return all_results


async def main():
    parser = argparse.ArgumentParser(description="DeepFlow Eval Runner")
    parser.add_argument("--agent", default="planner", help="要评测的 Agent (planner | all)")
    parser.add_argument("--output", help="输出 JSON 结果文件路径")
    args = parser.parse_args()

    # 校验配置
    missing = Config.validate()
    if missing:
        console.print(f"[red]配置缺失: {missing}[/red]")
        return 1

    if args.agent == "all":
        agents = ["planner"]
    else:
        agents = [args.agent]

    results = await eval_all(agents)

    # 保存结果
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        console.print(f"\n[dim]结果已保存到: {output_path}[/dim]")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
