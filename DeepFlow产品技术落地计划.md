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
- 工具：内置工具注册表 + 环境配置的远程 MCP Streamable HTTP 工具
- 模型：DeepSeek V4 Flash/Pro，保留国内外模型 Provider 接口

明确暂不采用：

- LangGraph
- PostgreSQL / Milvus / MinIO / Celery
- 复杂低代码画布
- 企业 SSO、计费、审批流

## 3. 当前实现总览

截至本轮提交，DeepFlow 已经从 CLI/Web MVP 扩展到 PRD 要求的主要产品闭环：

- 单用户研究主链路已具备完整功能闭环。
- 多用户可注册、登录并隔离个人数据。
- 用户可上传私域知识库并生成可追溯引用。
- 报告可编辑、保存版本、恢复版本、导出 Markdown/PDF。
- 可生成 PPTX、播客脚本和文本处理结果。
- 可管理内置与远程 MCP 工具，并在工作流节点中测试和调用。
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
- 固定预算档位、耗时、token、模型费用、搜索调用和 Tavily credits 统计。
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
- `arxiv_search`
- `knowledge_search`
- `python_sandbox`

远程 MCP：

- 使用 `MCP_TOOLS_JSON` 显式登记服务 URL、工具名和认证环境变量名。
- 支持 Streamable HTTP `initialize` 与 `tools/call`。
- 可作为配置式工作流中的 `MCP Tool` 节点执行，调用结果进入节点 Trace。

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

工具启用状态已按用户持久化到 SQLite，服务重启后保持不变。公网演示默认不配置远程 MCP；当前不做插件市场、OAuth 安装流程或复杂审批。

## 12. Coder Agent 与 Python 沙箱

### 当前实现

- Python 代码生成。
- Docker 隔离执行；公共 API 禁止回退到本机 subprocess。
- 危险操作拦截。
- 执行超时。
- 输出截断。
- 错误捕获。
- Trace 记录。

### 当前边界

公共部署默认关闭 Python 沙箱。只有 Docker readiness 正常并配置资源、网络与只读文件系统限制后才开放 Coder。

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

固定验证：

```bash
python -m pytest backend/tests -q
python -m pytest evals/tests -q
python -m compileall cli backend evals
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e
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

## 19. 求职演示版低成本稳定化

当前研究模型与预算策略：

| 档位 | 步骤 | 每步搜索 | 每步抓取 | Token 上限 | Tavily |
| --- | ---: | ---: | ---: | ---: | --- |
| 快速 | 3 | 1 | 1 | 50,000（报告预留 10,000） | basic |
| 标准 | 5 | 2 | 2 | 90,000（报告预留 20,000） | basic |
| 深度 | 8 | 3 | 3 | 160,000（报告预留 35,000） | advanced |

- Planner、Researcher 使用 `deepseek-v4-flash`，快速 Reporter 使用 Flash。
- 标准/深度 Reporter 使用 `deepseek-v4-pro`。
- 所有 V4 请求默认关闭 thinking。
- 每次调用前执行预算检查，恢复和重试沿用原任务预算。
- 价格表记录版本，兼容保留 `cost_rmb`。
- Provider 真实探测按需启用并缓存 10 分钟。
- Live Eval 需要环境变量与命令行双重开关，正式计划最多 12 次真实任务。
- 2026-07-28 真实评估共消耗 12 次、预计 ¥0.2813 和 38 Tavily credits；最终快速样本引用有效率 100%，但整体完成率尚未达到 90%。
- 公网演示使用 Vercel Hobby + Render Free；免费 Render 的 SQLite 不承诺重启后持久化。

## 20. 后续生产化建议

当前版本已覆盖 PRD 的核心功能表面和主要交互闭环，但不能仅凭功能存在就宣称达到全部产品目标。最新代码尚未重新执行付费 Live Eval，因此“90% 无人工干预完成率”“20+ 有效来源”和目标用户评分仍是待验证指标。

本轮已经完成：

- 报告风格切换统一鉴权、保存旧版本并同步新正文。
- Provider 真实探测要求登录、限流、10 分钟缓存并复用并发请求。
- 报告完成前检查标题、总结、分析、来源和引用；质量失败可重试。
- 预算提前收尾时记录完整/部分覆盖、完成问题和跳过问题。
- 来源接口返回标题、摘要、发布时间、可信度和对应研究步骤。
- 来源接口提取引用所在论述，建立轻量 claim-to-evidence 映射。
- 知识库记录 embedding Provider、模型、维度和索引版本，配置变化时提示重建。
- 最多三轮的规则化渐进澄清，不新增 LLM 成本。
- 支持自然语言修改计划、自动确认计划 API 和基于报告证据追问。
- 标准/深度档在 Planner 前执行一次可降级背景搜索，快速档保持零额外规划搜索。
- 技术/论文研究可在预算允许时补充 arXiv 学术来源。
- 远程 MCP 支持 `initialize`、`tools/call`、用户级启停、测试和工作流 Trace。
- 离线验证结果：后端 55 项测试通过，前端 7 项 Playwright E2E 通过，Lint 与生产构建通过。

仍需真实环境验证或生产化增强：

- 大文件解析与并发上传压力测试。
- embedding/rerank provider 的失败降级和重试策略。
- Python 沙箱进一步评估 Firecracker 等更强隔离。
- 更完整的权限 E2E。
- 更细粒度的 Agent Eval。
- 更完整的成本告警。
- 数据库从 SQLite 迁移到 PostgreSQL/pgvector 的生产方案。
- 在明确批准的少量预算下重新执行固定 Live Eval，验证本轮预算和报告质量修复是否把成功率提升到目标值。

## 21. 最终目标

DeepFlow 最终要达到：

- 单用户可稳定完成深度研究。
- 多用户可登录并管理自己的研究资产。
- 企业用户可上传私域知识库并生成可追溯报告。
- 内容用户可生成 Markdown、PDF、PPTX、播客脚本和音频。
- 高级用户可接入工具并配置自己的 Agent 工作流。
- 团队用户可协作、评论、共享和复用模板。
- 系统具备成本控制、Agent Trace、错误降级和可观测性。
