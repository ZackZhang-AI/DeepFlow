# DeepFlow

DeepFlow 是一个面向深度研究场景的多 Agent AI 工作台。用户输入研究主题后，系统会完成澄清、规划、资料检索、私域知识库召回、代码分析、报告生成与成果物导出，并提供个人资产管理、团队协作、研究模板和配置式 Agent 工作流。

当前版本严格围绕 `AI产品需求文档.pdf` 落地，继续保持轻量架构：FastAPI + SQLite + Next.js，不引入 Milvus、MinIO、Celery、LangGraph 或额外企业平台能力。

## 已实现能力

### 研究主流程

- 用户注册、登录、会话鉴权。
- 创建研究任务，支持澄清问题、研究计划生成、计划确认。
- 研究任务通过 SQLite 持久化队列执行，支持进程重启恢复、失败阶段重试和 SSE 事件重放。
- 多 Agent 流程：Coordinator、Planner、Researcher、Coder、Reporter、Artifact。
- SSE 进度事件与 Agent Trace。
- 资源权限：个人资源按用户隔离；团队资源按 Workspace 的 owner/editor/viewer 角色访问。
- 成本与预算控制字段：搜索次数、抓取次数、token、耗时、费用、错误记录。

### 私域知识库与 RAG

- 支持上传/创建 PDF、TXT、Markdown 文档。
- 文档状态：`pending | processing | ready | failed`。
- 文档解析、分块、页码和 metadata 保留。
- embedding 入库到 SQLite。
- 默认 `EMBEDDING_PROVIDER=auto`：配置 DashScope Key 时使用云 embedding，否则自动使用零成本本地 hashing embedding。
- hybrid 检索：向量召回 + 关键词召回 + 可选 rerank。
- 新建研究时可显式启用知识库并选择文档，任务只召回所选且状态为 `ready` 的资料。
- 研究报告引用统一使用 `kb://{doc_id}#{chunk_id}`。
- 报告中的知识库引用可点击定位到具体 chunk 和页码。
- 前端知识库面板支持查看文档状态、错误原因、chunk、页码、分数和召回模式。

### Coder Agent 与 Python 沙箱

- 支持 Python 代码生成与 Docker 沙箱执行；公共 API 不允许降级到本机 subprocess。
- 执行超时、危险操作拦截、输出长度限制。
- 错误捕获与简单自动修复入口。
- Trace 记录代码工具调用、耗时、错误和结果摘要。

### 报告与成果物

- Markdown 报告生成、查看和编辑。
- 报告版本管理：保存版本、查看版本、恢复版本。
- 文本处理：润色、扩写、缩写、指定章节改写。
- 导出：Markdown、PDF。
- 成果物：PPTX、播客脚本、可选本机 TTS 接口。
- 个人资产中心展示研究任务、报告、知识库、PPTX、播客等资产。

### MCP 工具管理

- 内置工具注册表：
  - `web_search`
  - `knowledge_search`
  - `python_sandbox`
- 工具列表、启用/禁用、测试调用。
- 测试结果包含输入摘要、输出摘要、耗时、错误和原始输出。
- 前端 `/tools` 工具管理页。

### 团队协作

- Workspace 与 Project。
- 权限角色：`owner | editor | viewer`。
- owner 唯一且不可被普通成员变更；editor 可创建和编辑，viewer 严格只读。
- 团队成员可共同访问绑定到 Workspace/Project 的任务、知识库、报告版本和成果物。
- 报告评论。
- 只读共享链接。
- 个人模式兼容，不强制创建团队空间。
- 前端 `/workspaces` 与 `/shared/[token]` 页面。

### 研究模板

- 模板 CRUD。
- 模板字段：名称、分类、描述、默认澄清问题、默认计划结构、推荐搜索域、报告风格。
- 支持从模板创建研究任务。
- 前端 `/templates` 页面。

### 自定义 Agent 工作流

- 基于当前 Python 状态机的配置式工作流，不迁移 LangGraph。
- 支持节点：Planner、Researcher、Coder、Reporter、Artifact、Human Feedback、MCP Tool。
- 支持顺序执行、失败重试、预算限制、Human Feedback 暂停/继续、运行记录和节点 Trace。
- 前端 `/workflows` 页面。

## 技术栈

| 层级 | 选择 |
| --- | --- |
| 后端 | Python, FastAPI, SQLite, Pydantic |
| 前端 | Next.js 16, React, TypeScript, Tailwind CSS |
| Agent 编排 | Python asyncio 状态机 |
| 私域知识库 | SQLite 存储 chunk 和 embedding |
| 搜索 | Tavily 或兼容搜索 Provider |
| 模型 | DeepSeek V4 Flash/Pro；保留 DashScope/OpenAI 兼容 Provider |
| 沙箱 | Docker 隔离执行；公共 API 禁止回退到本机 subprocess |
| 导出 | Markdown, PDF, PPTX, 播客脚本 |

## 低成本研究模式

研究任务只能选择固定预算档位，后端会持久化实际限制并在每次模型、搜索和抓取调用前检查余额：

| 档位 | 步骤 | 每步搜索 | 每步抓取 | Token 上限 | Tavily |
| --- | ---: | ---: | ---: | ---: | --- |
| 快速 | 3 | 1 | 1 | 30,000 | basic |
| 标准 | 5 | 2 | 2 | 60,000 | basic |
| 深度 | 8 | 3 | 3 | 100,000 | advanced |

- Planner、Researcher 默认使用 `deepseek-v4-flash`。
- 快速报告使用 Flash，标准/深度报告使用 `deepseek-v4-pro`。
- DeepSeek V4 显式关闭 thinking，费用按版本化价格表估算。
- 任务页展示 token、人民币预估费用、搜索/抓取次数和 Tavily credits。
- `402` 会立即标记为 `provider_balance_exhausted`，不会自动重试。

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/ZackZhang-AI/DeepFlow.git
cd DeepFlow

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd frontend
npm install
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，按需填写模型、搜索、embedding 与 rerank 配置。

```bash
copy .env.example .env
```

最小可运行配置通常包括：

```env
DEEPSEEK_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
```

私域知识库默认无需额外 Key：`EMBEDDING_PROVIDER=auto` 会在没有 DashScope Key 时使用本地 embedding。若需要更强的语义召回或 rerank，再配置 `DASHSCOPE_API_KEY`。

### 私域知识库使用流程

1. 登录后在研究首页展开“私域知识库”。
2. 上传 PDF、TXT、Markdown，或直接粘贴文本。
3. 等待状态变为“可检索”，可先输入问题测试召回结果。
4. 在研究范围中开启“使用私域知识库”，勾选本次研究要使用的资料。
5. 创建并执行研究；知识库来源会以 `kb://{doc_id}#{chunk_id}` 出现在来源检查中，可定位到原始 chunk 和页码。

### 3. 启动后端

```bash
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务与接口文档：

| 服务 | 地址 |
| --- | --- |
| API | `http://localhost:8000` |
| Swagger | `http://localhost:8000/docs` |
| 健康检查 | `http://localhost:8000/api/health` |
| Provider 配置检查 | `http://localhost:8000/api/system/readiness` |
| Provider 真实探测 | `http://localhost:8000/api/system/readiness?probe=true` |

### 4. 启动前端

```bash
cd frontend
npm run dev -- --port 3001
```

浏览器打开：

```text
http://localhost:3001
```

当前项目固定使用 `3001`，避免与其他 DeepFlow 工作目录占用的 `3000` 端口混淆。若使用其他端口，请同步将其加入 `.env` 的 `CORS_ORIGINS`。

### 5. 默认本地账号

首次启动后端时，系统会根据 `.env` 自动创建本地演示账号：

```text
账号：deepflow
密码：DeepFlow2026!
```

该账号只用于本地开发和功能演示。公开部署前必须修改 `DEMO_USERNAME`、`DEMO_PASSWORD`，并建议设置 `ALLOW_PUBLIC_REGISTRATION=false`。演示账号只在首次不存在时创建；修改密码后如需更新已有账号，请重新注册新账号或清理本地演示数据库。

## 主要页面

| 页面 | 说明 |
| --- | --- |
| `/login` | 登录与注册 |
| `/` | 新建研究与最近任务 |
| `/research/[taskId]` | 可恢复的研究详情、计划、进度、来源和报告工作区 |
| `/history` | 个人资产中心 |
| `/tools` | MCP 工具管理 |
| `/templates` | 研究模板 |
| `/workflows` | 自定义 Agent 工作流 |
| `/workspaces` | 团队空间与协作 |
| `/shared/[token]` | 只读共享页 |

## API 概览

| 模块 | 代表接口 |
| --- | --- |
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` |
| System | `GET /api/system/readiness?probe=true` |
| Research | `GET /api/research-tasks/{id}`, `POST /api/research-tasks/{id}/retry`, `GET /api/research-tasks/{id}/events?after_seq=` |
| Research | `POST /api/research-tasks`, `GET /api/research-tasks/{id}`, `POST /api/research-tasks/{id}/confirm-plan` |
| Usage | `GET /api/research-tasks/usage-summary` |
| Report | `GET /api/reports/{task_id}`, `PATCH /api/reports/{task_id}`, `GET /api/reports/{task_id}/download` |
| Report Version | `GET /api/reports/{task_id}/versions`, `POST /api/reports/{task_id}/versions/{version_id}/restore` |
| Knowledge | `POST /api/knowledge-documents/upload`, `GET /api/knowledge-documents/search`, `GET /api/knowledge-documents/{doc_id}/chunks` |
| Artifacts | `POST /api/artifacts/ppt`, `POST /api/artifacts/podcast`, `GET /api/artifacts/download/{artifact_id}` |
| Tools | `GET /api/tools`, `PATCH /api/tools/{tool_id}`, `POST /api/tools/{tool_id}/test` |
| Workspaces | `GET /api/workspaces`, `POST /api/workspaces`, `POST /api/workspaces/{id}/members` |
| Templates | `GET /api/templates`, `POST /api/templates`, `POST /api/templates/{id}/start-research` |
| Workflows | `GET /api/workflows`, `POST /api/workflows`, `POST /api/workflows/{id}/runs` |

## 验证命令

本轮实现已通过以下验证：

```bash
python -m pytest backend/tests -q
python -m compileall cli backend evals
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e
```

真实质量评估默认是 dry-run，不会调用付费 API：

```bash
python -m evals.live_eval --formal
```

只有同时设置 `RUN_LIVE_E2E=1` 并显式传入 `--live` 才会执行真实研究。正式计划固定为 8 次快速、2 次标准，包含重试最多 12 次；原始结果写入已忽略的 `evals/results/`。

2026-07-28 的受控评估消耗 12 次真实任务，模型预计费用 ¥0.2813、Tavily 38 credits。三个最终快速样本完成且引用有效率 100%；整体完成率未达到 90% 目标，详见 `evals/examples/live_eval_summary_2026-07-28.md`。达到硬上限后未继续付费重测。

## 当前边界

- 当前默认使用 SQLite，适合原型、MVP 和单机验证；大规模生产部署前建议评估 PostgreSQL/pgvector。
- 工具启用状态按用户持久化到 SQLite。
- 私域知识库已具备 PRD 所需检索闭环，但未引入 Milvus、MinIO、Celery、RAGAS 等 PRD 外企业栈。
- 工作流为顺序配置式可运行版本；`edges` 尚不参与条件分支执行。
- 公共部署默认 `DISABLE_SANDBOX_TOOL=true`；只有 Docker readiness 正常时才应开启 Coder。
- 云 TTS、计费、企业 SSO、复杂审批流不在当前 PRD 实现范围内。

## 项目结构

```text
DeepFlow/
├── backend/                 # FastAPI 后端
│   └── app/
│       ├── api/routes/      # auth, research, report, artifacts, knowledge, tools, workspaces, templates, workflows
│       ├── core/            # 连接迁移、鉴权、访问策略、事件与任务队列
│       ├── repositories/    # 按领域拆分的 SQLite 数据访问层
│       └── services/        # research, knowledge, embedding, tools
├── cli/                     # Agent 引擎与状态机
│   ├── agents/              # Planner, Researcher, Coder, Reporter 等
│   └── tools/               # web_search, sandbox
├── frontend/                # Next.js 前端
│   ├── app/                 # 页面路由
│   ├── components/          # 报告、知识库、成果物、Trace 等组件
│   ├── e2e/                 # Playwright 研究闭环与响应式回归
│   └── lib/                 # API wrapper 与类型
├── prompts/                 # Agent Prompt
├── evals/                   # Eval 用例和 runner
└── backend/tests/           # smoke 测试
```

## License

MIT

## Demo Deployment Notes

This repo is prepared for a controlled job-search demo deployment:

- Frontend: deploy `frontend/` to Vercel.
- Backend: deploy the repository to Render as a Web Service.
- Render start command:
  ```bash
  python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
  ```
- Render 免费实例没有持久磁盘，休眠或重启后 SQLite 数据可能丢失；求职演示通过启动时创建演示账号和示例模板恢复基础入口。
- 需要保留历史数据时，升级到支持 persistent disk 的实例并设置 `DEEPFLOW_DB_PATH=/var/data/deepflow.db`。
- Vercel environment: set `NEXT_PUBLIC_API_URL` to the Render backend URL.
- Render environment: set `CORS_ORIGINS` to the exact Vercel origin.

Recommended public demo settings:

```env
ALLOW_PUBLIC_REGISTRATION=false
DEMO_USERNAME=interviewer
DEMO_PASSWORD=<strong-demo-password>
DISABLE_SANDBOX_TOOL=true
RATE_LIMIT_WINDOW_SECONDS=3600
RESEARCH_TASK_RATE_LIMIT_PER_HOUR=10
TOOL_TEST_RATE_LIMIT_PER_HOUR=10
KNOWLEDGE_WRITE_RATE_LIMIT_PER_HOUR=10
ARTIFACT_RATE_LIMIT_PER_HOUR=10
KNOWLEDGE_UPLOAD_MAX_BYTES=5242880
```

`DEMO_PASSWORD` 必须在 Render Secret 中单独设置，不能使用 README 中公开的本地默认密码。Vercel Hobby 与 Render Free 可用于阶段性个人演示，现金部署成本为 0；免费后端不承诺历史数据持久化。

Demo boundaries:

- SQLite is intentionally kept for the demo; use PostgreSQL/pgvector before operating this as a real multi-user product.
- Public registration should stay disabled for interview/demo links.
- Python sandbox testing should stay disabled unless the backend runs it with container isolation.
- Keep API keys in platform environment variables only; never commit `.env`.
