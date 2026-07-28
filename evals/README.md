# DeepFlow Eval

## 安全默认值

`live_eval` 默认只执行 dry-run，不会登录后端，也不会调用模型或搜索 API：

```powershell
python -m evals.live_eval
python -m evals.live_eval --case technical
python -m evals.live_eval --formal
```

真实调用必须同时提供 `--live` 和 `RUN_LIVE_E2E=1`。单案例是默认真实执行方式：

```powershell
$env:RUN_LIVE_E2E = "1"
$env:LIVE_EVAL_USERNAME = "deepflow"
$env:LIVE_EVAL_PASSWORD = "<local-secret>"
python -m evals.live_eval --live --case market
```

正式评估固定为五类案例各两次，共 10 次。进程内包含重试在内最多消费 12 次任务尝试：

```powershell
python -m evals.live_eval --live --formal
```

若正式评估曾被人工中断，可用 `--skip` 从固定计划中续跑，并用 `--attempt-limit`
收紧本次剩余额度；尝试上限不能超过 12。

可选环境变量：

- `LIVE_EVAL_BASE_URL`：默认 `http://localhost:8000`。
- `DEEPFLOW_DB_PATH`：本地 SQLite 路径，用于只读校验任务实际记录的来源。

当前后端 API 没有公开研究步骤的完整来源列表。对本地评估，Runner 会以只读方式查询
`research_steps.sources_json`；远程 API 若没有返回 `recorded_sources`、`sources` 或
`references`，引用追溯检查会明确失败，而不会使用报告链接自证。

原始结果和运行时脱敏摘要写入被 Git 忽略的 `evals/results/`。仓库只保留
`live_eval_summary.schema.json` 和 `examples/live_eval_summary.example.json`。

离线验证不会触发付费 API：

```powershell
python -m pytest evals/tests -q
python -m evals.live_eval --formal
```
