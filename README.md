# DeepFlow

DeepFlow 是一个面向深度研究场景的多 Agent AI 工作台。用户输入研究主题后，系统会完成澄清、规划、资料检索、私域知识库召回、代码分析、报告生成与成果物导出，并提供个人资产管理、团队协作、研究模板和配置式 Agent 工作流。

当前版本严格围绕 `AI产品需求文档.pdf` 落地，继续保持轻量架构：FastAPI + SQLite + Next.js，不引入 Milvus、MinIO、Celery、LangGraph 或额外企业平台能力。

## 已实现能力

### 研究主流程

- 用户注册、登录、会话鉴权。
- 创建研究任务，支持澄清问题、研究计划生成、计划确认。
- 多 Agent 流程：Coordinator、Planner、Researcher、Coder、Reporter、Artifact。
- SSE 进度事件与 Agent Trace。
- 用户隔离：任务、报告、知识库、成果物默认只能由当前用户访问。
- 成本与预算控制字段：搜索次数、抓取次数、token、耗时、费用、错误记录。

### 私域知识库与 RAG

- 支持上传/创建 PDF、TXT、Markdown 文档。
- 文档状态：`pending | processing | ready | failed`。
- 文档解析、分块、页码和 metadata 保留。
- embedding 入库到 SQLite。
- hybrid 检索：向量召回 + 关键词召回 + 可选 rerank。
- 研究报告引用统一使用 `kb://{doc_id}#{chunk_id}`。
- 前端知识库面板支持查看文档状态、错误原因、chunk、页码、分数和召回模式。

### Coder Agent 与 Python 沙箱

- 支持 Python 代码生成与沙箱执行。
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
- 支持顺序执行、失败重试、预算限制、运行记录和节点 Trace。
- 前端 `/workflows` 页面。

## 技术栈

| 层级 | 选择 |
| --- | --- |
| 后端 | Python, FastAPI, SQLite, Pydantic |
| 前端 | Next.js 16, React, TypeScript, Tailwind CSS |
| Agent 编排 | Python asyncio 状态机 |
| 私域知识库 | SQLite 存储 chunk 和 embedding |
| 搜索 | Tavily 或兼容搜索 Provider |
| 模型 | DeepSeek / DashScope / OpenAI 兼容 Provider |
| 沙箱 | 本地 Python 子进程，预留 Docker 模式 |
| 导出 | Markdown, PDF, PPTX, 播客脚本 |

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

如需启用知识库 embedding/rerank，可配置对应 Provider 的 Key。

### 3. 启动后端

```bash
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 启动前端

```bash
cd frontend
npm run dev
```

浏览器打开：

```text
http://localhost:3000
```

## 主要页面

| 页面 | 说明 |
| --- | --- |
| `/login` | 登录与注册 |
| `/` | 研究工作台 |
| `/history` | 个人资产中心 |
| `/tools` | MCP 工具管理 |
| `/templates` | 研究模板 |
| `/workflows` | 自定义 Agent 工作流 |
| `/workspaces` | 团队空间与协作 |
| `/shared/[token]` | 只读共享页 |

## API 概览

| 模块 | 代表接口 |
| --- | --- |
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| Research | `POST /api/research-tasks`, `GET /api/research-tasks/{id}`, `POST /api/research-tasks/{id}/confirm-plan` |
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
python -m pytest backend/tests/test_wave0_smoke.py -q
python -m compileall cli backend evals
npm.cmd run lint
npm.cmd run build
```

FastAPI import smoke：

```text
DeepFlow API
65 routes
```

## 当前边界

- 当前默认使用 SQLite，适合原型、MVP 和单机验证；大规模生产部署前建议评估 PostgreSQL/pgvector。
- 工具启用状态目前为内存态，服务重启后恢复默认。
- 私域知识库已具备 PRD 所需检索闭环，但未引入 Milvus、MinIO、Celery、RAGAS 等 PRD 外企业栈。
- 工作流为配置式可运行版本，未实现复杂低代码画布。
- 云 TTS、计费、企业 SSO、复杂审批流不在当前 PRD 实现范围内。

## 项目结构

```text
DeepFlow/
├── backend/                 # FastAPI 后端
│   └── app/
│       ├── api/routes/      # auth, research, report, artifacts, knowledge, tools, workspaces, templates, workflows
│       ├── core/            # auth, db, events
│       └── services/        # research, knowledge, embedding, tools
├── cli/                     # Agent 引擎与状态机
│   ├── agents/              # Planner, Researcher, Coder, Reporter 等
│   └── tools/               # web_search, sandbox
├── frontend/                # Next.js 前端
│   ├── app/                 # 页面路由
│   ├── components/          # 报告、知识库、成果物、Trace 等组件
│   └── lib/                 # API wrapper 与类型
├── prompts/                 # Agent Prompt
├── evals/                   # Eval 用例和 runner
└── backend/tests/           # smoke 测试
```

## License

MIT
