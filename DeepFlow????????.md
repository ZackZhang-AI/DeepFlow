# DeepFlow 产品技术落地计划与当前实现状态

本文档用于说明 DeepFlow 从 PRD 到工程实现的技术路线、当前已实现能力、后续生产化边界和验收方式。当前实现只覆盖 `AI产品需求文档.pdf` 中要求的产品能力，不引入 `ragPdfSystem` 中 PRD 外的企业级平台能力，例如 Milvus、MinIO、Celery、RabbitMQ、RAGAS、Vue 管理平台等。

## 1. 项目定位

DeepFlow 是一个深度研究 Agent 工作台。用户输入研究主题后，系统通过多个 Agent 协作完成：

```text
主题输入 -> 澄清问题 -> 研究计划 -> 资料搜索/知识库召回 -> 分析处理 -> 报告生成 -> 成果物输出
```

产品目标不是一个普通聊天机器人，而是可追踪、可编辑、可复用、可协作的研究生产系统。

## 2. 技术路线

当前继续采用轻量工程路线：

- 后端：FastAPI + SQLite
- 前端：Next.js + React + TypeScript + Tailwind CSS
- Agent 编排：Python asyncio 状态机
- RAG：SQLite 存储文档、chunk、embedding
- 工具：内置工具注册表，预留 MCP 扩展
- 模型：保留国内外模型 Provider 接口

明确暂不采用：

- LangGraph
- PostgreSQL / Milvus / MinIO / Celery
- 复杂低代码画布
- 企业 SSO、计费、审批流

## 3. 当前实现总览

截至本轮提交，DeepFlow 已经从 CLI/Web MVP 扩展到 PRD 要求的主要产品闭环：

- 单用户可完成深度研究。
- 多用户可注册、登录并隔离个人数据。
- 用户可上传私域知识库并生成可追溯引用。
- 报告可编辑、保存版本、恢复版本、导出 Markdown/PDF。
- 可生成 PPTX、播客脚本和文本处理结果。
- 可管理 MCP 工具并测试调用。
- 可创建团队空间、项目、报告评论和只读共享链接。
- 可创建研究模板并从模板启动研究。
- 可配置并运行简化 Agent 工作流。
- 系统具备 Agent Trace、成本字段、错误降级和 smoke 测试。

## 4. Phase 0：CLI 原型

### 目标

用命令行先验证核心研究闭环：

```text
输入主题 -> Planner 生成计划 -> Researcher 搜索资料 -> Reporter 生成 Markdown 报告
```

### 当前状态

已实现。

### 关键能力

- CLI 研究任务入口。
- Planner、Researcher、Coder、Reporter Agent。
- Python asyncio 状态机。
- 搜索、抓取、报告生成。
- 本地输出和运行日志。
- prompt 版本化管理。

## 5. Phase 1：极简 Web MVP

### 目标

将核心研究闭环搬到 Web 页面：

```text
输入主题 -> 展示计划 -> 用户确认 -> 执行研究 -> 展示报告
```

### 当前状态

已实现并增强。

### 关键能力

- Next.js 研究工作台。
- FastAPI 研究任务 API。
- SSE 进度事件。
- 计划确认、拒绝、轻量编辑。
- 报告查看与基础成果物操作。

## 6. Phase 2：工程化增强

### 目标

让系统具备可长期迭代的工程结构，而不是一次性 Demo。

### 当前状态

核心能力已实现。

### 已实现能力

- 用户注册、登录、token/session。
- 当前用户鉴权。
- 用户 A/B 数据隔离。
- 任务历史与个人资产中心。
- Agent Trace。
- 报告版本管理。
- Markdown/PDF 导出。
- PPTX 与播客脚本。
- Coder Agent 与 Python 沙箱。
- 成本、耗时、token、工具调用统计字段。
- 后端 smoke 测试。

## 7. Phase 3：产品化扩展

### 目标

补齐 PRD 中的专业工作台能力。

### 当前状态

PRD 要求的最小闭环已实现。

### 已实现能力

- 私域知识库 / RAG。
- MCP 工具管理。
- 多报告风格与文本处理。
- Workspace / Project。
- owner / editor / viewer 权限。
- 报告评论。
- 只读共享链接。
- 研究模板。
- 配置式 Agent 工作流。

## 8. Agent 设计方案

当前 Agent 分工如下：

| Agent | 职责 |
| --- | --- |
| Coordinator | 识别研究意图和澄清需求 |
| Planner | 生成结构化研究计划 |
| Researcher | 搜索公开资料，召回私域知识库，整理 findings |
| Coder | 生成并执行 Python 分析代码 |
| Reporter | 生成结构化 Markdown 报告 |
| Artifact | 生成 PPTX、播客脚本、文本处理结果 |

Agent Trace 已记录：

- Agent 名称
- phase
- status
- input/output summary
- tool calls
- token
- elapsed seconds
- error

## 9. Prompt 工程化方案

PRD 中的系统提示词不直接照搬，而是拆成工程化结构：

- Agent Card：定义角色、边界、输入、输出和工具依赖。
- Prompt Template：保存可版本化 prompt。
- Output Schema：用 Pydantic/TypeScript 约束输出结构。
- Eval Spec：为 Planner、Researcher、Reporter 等关键 Agent 提供评估依据。

当前已对 Researcher prompt 增加私域知识库引用规则：

```text
知识库来源必须保留 kb://{doc_id}#{chunk_id}
不得伪装成公开网页链接
```

## 10. RAG / 私域知识库

### 当前实现

- 文档上传与手动创建。
- 支持 PDF、TXT、Markdown。
- 文档状态：`pending | processing | ready | failed`。
- 解析文本、页码、metadata。
- chunk 分块。
- embedding 生成并存入 SQLite。
- hybrid 检索。
- 可选 rerank。
- 检索结果包含：
  - `doc_id`
  - `chunk_id`
  - `chunk_index`
  - `content/preview`
  - `score`
  - `source_name`
  - `page_num`
  - `retrieval_mode`
- 报告引用格式统一为：

```text
kb://{doc_id}#{chunk_id}
```

### 前端能力

- 知识库文档列表。
- 上传文档。
- 查看状态、错误原因和 chunk 数。
- 检索调试面板。
- 查看召回 chunk、页码、分数和召回模式。

## 11. MCP 工具集成

### 当前实现

内置工具注册表：

- `web_search`
- `knowledge_search`
- `python_sandbox`

API：

- `GET /api/tools`
- `PATCH /api/tools/{tool_id}`
- `POST /api/tools/{tool_id}/test`

前端：

- `/tools` 工具管理页。
- 工具启用/禁用。
- JSON 参数测试。
- 返回 success、input_summary、output_summary、elapsed_seconds、error、raw_output。

### 当前边界

工具启用状态为内存态，服务重启会恢复默认。后续生产化可持久化到数据库。

## 12. Coder Agent 与 Python 沙箱

### 当前实现

- Python 代码生成。
- 本地沙箱执行。
- 危险操作拦截。
- 执行超时。
- 输出截断。
- 错误捕获。
- Trace 记录。

### 当前边界

当前以本地子进程为主，生产环境建议启用 Docker 或专用隔离运行时。

## 13. 报告与成果物

### 已实现

- Markdown 报告查看。
- 报告编辑保存。
- 报告版本列表。
- 版本详情。
- 版本恢复。
- Markdown/PDF 下载。
- PPTX 生成与下载。
- 播客脚本生成。
- 可选本机 TTS 接口。
- 文本润色、扩写、缩写、指定章节改写。

### 报告风格

当前支持面向 PRD 的多风格扩展：

- 通用研究报告
- 市场分析
- 竞品分析
- 技术调研
- 投资分析

## 14. 多人协作

### 已实现

- Workspace。
- Project。
- 角色：`owner | editor | viewer`。
- 成员管理。
- 项目创建。
- 报告评论。
- 只读共享链接。
- 公共只读页 `/shared/[token]`。

### 当前边界

未实现企业 SSO、审计日志、复杂审批流和计费系统。

## 15. 研究模板

### 已实现

模板包含：

- 名称
- 分类
- 描述
- 默认澄清问题
- 默认计划结构
- 推荐搜索域
- 报告风格

能力：

- 创建模板
- 编辑模板
- 删除模板
- 查看模板
- 从模板创建研究任务

前端页面：

```text
/templates
```

## 16. 自定义 Agent 工作流

### 已实现

支持节点：

- Planner
- Researcher
- Coder
- Reporter
- Artifact
- Human Feedback
- MCP Tool

支持能力：

- nodes JSON 配置
- edges JSON 配置
- budget JSON 配置
- 顺序执行
- 失败重试
- 运行记录
- 节点 Trace

前端页面：

```text
/workflows
```

### 当前边界

当前不做复杂低代码画布，也不迁移 LangGraph。

## 17. 数据结构与接口设计

核心数据库表包括：

- `users`
- `auth_sessions`
- `research_tasks`
- `research_steps`
- `knowledge_documents`
- `knowledge_chunks`
- `report_versions`
- `artifacts`
- `agent_runs`
- `workspaces`
- `workspace_members`
- `projects`
- `report_comments`
- `shared_links`
- `research_templates`
- `workflows`
- `workflow_runs`
- `workflow_node_runs`

所有新增资源默认按当前用户隔离；团队资源通过 workspace/project 进行协作访问。

## 18. 测试与验收

已通过验证：

```bash
python -m pytest backend/tests/test_wave0_smoke.py -q
python -m compileall cli backend evals
npm.cmd run lint
npm.cmd run build
```

后端 smoke 覆盖：

- 注册登录。
- A/B 用户隔离。
- 报告导出。
- 成果物下载。
- 知识库基础检索。
- 工具列表、启用/禁用、测试调用。
- Workspace/Project 权限。
- 报告评论和分享链接。
- 模板创建与从模板启动研究。
- 工作流创建、运行与 Trace。

## 19. 后续生产化建议

当前版本已满足 PRD 功能闭环，但上线生产前建议继续增强：

- 大文件解析与并发上传压力测试。
- embedding/rerank provider 的失败降级和重试策略。
- 工具启用状态持久化。
- Python 沙箱切换到 Docker/Firecracker 等更强隔离。
- 更完整的权限 E2E。
- 更细粒度的 Agent Eval。
- 成本看板和预算告警。
- 数据库从 SQLite 迁移到 PostgreSQL/pgvector 的生产方案。

## 20. 最终目标

DeepFlow 最终要达到：

- 单用户可稳定完成深度研究。
- 多用户可登录并管理自己的研究资产。
- 企业用户可上传私域知识库并生成可追溯报告。
- 内容用户可生成 Markdown、PDF、PPTX、播客脚本和音频。
- 高级用户可接入工具并配置自己的 Agent 工作流。
- 团队用户可协作、评论、共享和复用模板。
- 系统具备成本控制、Agent Trace、错误降级和可观测性。
