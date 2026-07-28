#!/usr/bin/env python3
"""Cost-controlled DeepFlow live evaluation.

The command is dry-run by default. Network execution requires both
``RUN_LIVE_E2E=1`` and the explicit ``--live`` flag.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

from evals.live_eval_core import (
    ATTEMPT_HARD_LIMIT,
    AttemptBudget,
    EvaluationResult,
    LiveCase,
    LiveEvalError,
    build_formal_schedule,
    build_redacted_summary,
    collect_recorded_sources,
    ensure_live_enabled,
    evaluate_payload,
    extract_report_citations,
    load_cases as _load_cases,
)

ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = Path(__file__).with_name("live_cases.json")
RESULTS_DIR = Path(__file__).with_name("results")
TERMINAL_STATUSES = {"completed", "failed"}
PLAN_READY_STATUSES = {"clarifying", "awaiting_confirmation", "failed"}

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def load_cases(path: Path = CASES_PATH) -> list[LiveCase]:
    return _load_cases(path)


class DeepFlowAPI:
    def __init__(self, base_url: str, username: str, password: str, timeout: float = 30.0):
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)
        self.username = username
        self.password = password

    def close(self) -> None:
        self.client.close()

    def login(self) -> None:
        response = self.client.post(
            "/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
        data = _read_response(response, "登录失败")
        token = data.get("access_token")
        if not token:
            raise LiveEvalError("登录响应缺少 access_token")
        self.client.headers["Authorization"] = f"Bearer {token}"

    def create_task(self, case: LiveCase) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "topic": case.topic,
            "locale": "zh-CN",
            "max_steps": case.max_steps,
            "budget_profile": case.budget_profile,
        }
        if case.recency_days:
            payload["recency_days"] = case.recency_days
        return _read_response(
            self.client.post("/api/research-tasks", json=payload),
            "创建研究任务失败",
        )

    def get_task(self, task_id: str) -> dict[str, Any]:
        return _read_response(
            self.client.get(f"/api/research-tasks/{task_id}"),
            "读取研究任务失败",
        )

    def answer_clarifications(self, task_id: str, questions: Iterable[str]) -> None:
        answers = {
            str(index): "面向求职演示，优先使用可追溯的一手或权威来源，覆盖最近可用信息。"
            for index, _ in enumerate(questions)
        }
        _read_response(
            self.client.post(
                f"/api/research-tasks/{task_id}/clarifications",
                json={"answers": answers},
            ),
            "提交澄清回答失败",
        )

    def confirm_plan(self, task_id: str) -> None:
        _read_response(
            self.client.post(
                f"/api/research-tasks/{task_id}/confirm-plan",
                json={"action": "accept"},
            ),
            "确认研究计划失败",
        )

    def retry(self, task_id: str) -> None:
        _read_response(
            self.client.post(f"/api/research-tasks/{task_id}/retry"),
            "重试研究任务失败",
        )

    def get_report(self, task_id: str) -> dict[str, Any]:
        return _read_response(
            self.client.get(f"/api/reports/{task_id}"),
            "读取报告失败",
        )

    def get_agent_runs(self, task_id: str) -> list[dict[str, Any]]:
        data = _read_response(
            self.client.get(f"/api/research-tasks/{task_id}/agent-runs"),
            "读取 Agent Trace 失败",
        )
        return data if isinstance(data, list) else []


def run_case(
    api: DeepFlowAPI,
    case: LiveCase,
    budget: AttemptBudget,
    poll_seconds: float,
    timeout_seconds: float,
    db_path: Path | None,
) -> EvaluationResult:
    started = time.monotonic()
    attempt = budget.consume()
    task = api.create_task(case)
    task_id = str(task["task_id"])
    task = _wait_for(api, task_id, PLAN_READY_STATUSES, poll_seconds, timeout_seconds)
    if task.get("status") == "clarifying":
        api.answer_clarifications(task_id, task.get("clarification_questions") or [])
        task = _wait_for(api, task_id, PLAN_READY_STATUSES, poll_seconds, timeout_seconds)
    if task.get("status") == "failed":
        return _failure_result(case, attempt, task, started)

    api.confirm_plan(task_id)
    task = _wait_for(api, task_id, TERMINAL_STATUSES, poll_seconds, timeout_seconds)
    if task.get("status") == "failed" and task.get("retryable") and budget.used < budget.limit:
        attempt = budget.consume()
        api.retry(task_id)
        task = _wait_for(api, task_id, TERMINAL_STATUSES, poll_seconds, timeout_seconds)
    if task.get("status") != "completed":
        return _failure_result(case, attempt, task, started)

    report = api.get_report(task_id)
    agent_runs = api.get_agent_runs(task_id)
    sources = collect_recorded_sources(task, report, agent_runs, task_id, db_path)
    return evaluate_payload(
        case=case,
        attempt=attempt,
        task=task,
        report=report,
        agent_runs=agent_runs,
        recorded_sources=sources,
        elapsed_seconds=time.monotonic() - started,
    )


def _wait_for(
    api: DeepFlowAPI,
    task_id: str,
    statuses: set[str],
    poll_seconds: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        task = api.get_task(task_id)
        if task.get("status") in statuses:
            return task
        time.sleep(poll_seconds)
    raise LiveEvalError(f"任务 {task_id} 等待超时")


def _failure_result(
    case: LiveCase,
    attempt: int,
    task: dict[str, Any],
    started: float,
) -> EvaluationResult:
    return EvaluationResult(
        case_id=case.id,
        category=case.category,
        attempt=attempt,
        task_id=str(task.get("task_id") or ""),
        status=str(task.get("status") or "failed"),
        passed=False,
        completed_steps=_as_int(task.get("current_step")),
        elapsed_seconds=round(time.monotonic() - started, 3),
        error_code=str(task.get("error_code") or ""),
        error_message=str(task.get("error_message") or ""),
    )


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_response(response: httpx.Response, context: str) -> Any:
    if response.is_success:
        return response.json()
    try:
        detail = response.json()
    except ValueError:
        detail = response.text
    raise LiveEvalError(f"{context}: HTTP {response.status_code} {detail}")


def _default_db_path() -> Path:
    configured = os.getenv("DEEPFLOW_DB_PATH", "").strip()
    return Path(configured) if configured else ROOT / "backend" / "deepflow.db"


def _write_results(results: list[EvaluationResult], started_at: str) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_dir = RESULTS_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"live_eval_{stamp}.json"
    summary_path = RESULTS_DIR / f"summary_{stamp}.json"
    raw_path.write_text(
        json.dumps(
            {"started_at": started_at, "results": [asdict(result) for result in results]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(build_redacted_summary(results, started_at), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return raw_path, summary_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DeepFlow 受控 Live Eval")
    parser.add_argument("--live", action="store_true", help="执行真实 API；仍需 RUN_LIVE_E2E=1")
    parser.add_argument("--formal", action="store_true", help="运行固定 10 次正式评估")
    parser.add_argument("--case", default="market", help="dry-run/单案例 ID")
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="从正式计划开头跳过若干案例，仅用于中断后续跑",
    )
    parser.add_argument("--base-url", default=os.getenv("LIVE_EVAL_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument(
        "--attempt-limit",
        type=int,
        default=None,
        help="本进程真实任务尝试上限，最大 12；用于中断后收紧剩余额度",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        ensure_live_enabled(args.live)
        cases = load_cases()
        if args.skip < 0:
            raise LiveEvalError("skip 不能为负数")
        if args.formal:
            selected = build_formal_schedule(cases)[args.skip:]
            if not selected:
                raise LiveEvalError("skip 已超过正式计划长度")
        else:
            if args.skip:
                raise LiveEvalError("skip 只能与 --formal 一起使用")
            selected = [next(case for case in cases if case.id == args.case)]
        if not args.live:
            if args.formal:
                print(
                    f"DRY-RUN: 本次正式计划包含 {len(selected)} 次研究"
                    f"（已跳过 {args.skip} 次）；未发送任何 API 请求。"
                )
            else:
                case = selected[0]
                print(
                    f"DRY-RUN: {case.name} ({case.id}), "
                    f"profile={case.budget_profile}, max_steps={case.max_steps}。未发送任何 API 请求。"
                )
            return 0

        username = os.getenv("LIVE_EVAL_USERNAME", "").strip()
        password = os.getenv("LIVE_EVAL_PASSWORD", "")
        if not username or not password:
            raise LiveEvalError("真实评估需要 LIVE_EVAL_USERNAME 和 LIVE_EVAL_PASSWORD")
        requested_limit = args.attempt_limit or (len(selected) + 2)
        if requested_limit < 1 or requested_limit > ATTEMPT_HARD_LIMIT:
            raise LiveEvalError(
                f"attempt-limit 必须在 1 到 {ATTEMPT_HARD_LIMIT} 之间"
            )
        budget = AttemptBudget(limit=min(requested_limit, len(selected) + 2))
        api = DeepFlowAPI(args.base_url, username, password)
        started_at = datetime.now(timezone.utc).isoformat()
        results: list[EvaluationResult] = []
        try:
            api.login()
            for case in selected:
                results.append(
                    run_case(
                        api,
                        case,
                        budget,
                        args.poll_seconds,
                        args.timeout_seconds,
                        _default_db_path(),
                    )
                )
        finally:
            api.close()
        raw_path, summary_path = _write_results(results, started_at)
        print(f"Live Eval 完成：{sum(result.passed for result in results)}/{len(results)} 通过")
        print(f"原始结果：{raw_path}")
        print(f"脱敏摘要：{summary_path}")
        return 0 if all(result.passed for result in results) else 1
    except (LiveEvalError, StopIteration) as exc:
        print(f"Live Eval 已停止：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
