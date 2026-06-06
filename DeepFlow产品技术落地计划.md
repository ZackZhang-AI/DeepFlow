# DeepFlow 产品技术落地计划

## 1. 项目定位

DeepFlow 是一个面向深度研究场景的多 Agent AI 产品。用户只需要输入一个研究主题，系统即可自动完成需求理解、研究计划拆解、资料检索、网页读取、信息整理、报告生成，并在关键节点允许用户介入确认或调整。

本项目的定位不是简单的聊天机器人，也不是单次搜索摘要工具，而是一个能够持续扩展为专业研究工作台的 AI Agent 系统。它的核心价值在于把原本需要数小时甚至数天完成的资料收集、分析和报告撰写流程，压缩为可控、可追踪、可评估的自动化研究任务。

产品初期不追求一次性实现全部 PRD 能力，而是优先跑通最关键的研究闭环：

```text
输入主题 -> 生成计划 -> 执行搜索 -> 整理资料 -> 生成报告
```

后续再逐步加入 Web 体验、代码分析、私域知识库、报告编辑、多模态成果物和多人协作能力。

## 2. 核心目标

### 2.1 产品目标

- 将深度研究流程从人工多工具切换，转为一条自动化 Agent 工作流。
- 让用户能够快速得到结构化、带引用、可继续编辑的研究报告。
- 支持从轻量问题到复杂研究主题的渐进式处理。
- 在计划、执行、报告等关键节点提供透明状态和人工反馈能力。

### 2.2 MVP 目标

第一阶段 MVP 不做完整上线产品，而是验证核心 Agent 闭环是否稳定：

- 能否根据用户主题生成合理研究计划。
- 能否按计划执行搜索和资料整理。
- 能否生成结构清晰、引用可追踪的 Markdown 报告。
- 能否控制单次研究的成本、耗时和失败率。

### 2.3 长期目标

- 支持学术研究、市场调研、竞品分析、投资分析、技术研究、内容创作等多场景。
- 支持私域知识库、代码执行、PPT、播客脚本、报告版本管理。
- 支持团队协作、自定义 Agent 工作流和研究模板市场。

## 3. 分阶段路线

整体路线采用四个阶段：

```text
Phase 0: CLI 原型
Phase 1: 极简 Web MVP
Phase 2: 工程化增强
Phase 3: 产品化扩展
```

这样设计的原因是：Agent 系统最早的风险通常不在 UI，而在模型输出、工具调用、搜索质量、上下文组织和成本控制。先用 CLI 验证核心链路，可以更快暴露问题，避免一开始把复杂度花在登录、导出、历史记录、复杂前端状态上。

## 4. Phase 0：CLI 原型

### 4.1 阶段目标

用命令行在最短时间内跑通完整研究闭环：

```text
用户输入主题 -> Planner 生成计划 -> Researcher 执行搜索 -> Reporter 生成报告
```

### 4.2 包含功能

- 命令行输入研究主题。
- Planner Agent 生成 3-5 步研究计划。
- 用户在命令行确认计划。
- Researcher Agent 按步骤执行搜索。
- 抓取或摘要搜索结果。
- Reporter Agent 生成 Markdown 报告。
- 将报告保存到本地文件。
- 将运行日志保存到本地文件。
- 记录 token、耗时、工具调用次数、失败次数。

### 4.3 暂不包含

- Web UI。
- 登录和用户系统。
- 数据库持久化。
- 报告编辑。
- PDF 导出。
- 私域知识库。
- Coder Agent。
- PPT 和播客生成。
- 多人协作。

### 4.4 推荐技术

- Python 3.11+
- `asyncio` 手写状态机
- `pydantic` 定义输入输出 Schema
- `httpx` 调用模型和搜索 API
- `rich` 展示 CLI 状态
- SQLite 可选，用于记录任务日志
- Markdown 文件保存最终报告

### 4.5 状态机流程

```text
INIT
  -> PLAN_CREATED
  -> PLAN_CONFIRMED
  -> RESEARCH_RUNNING
  -> RESEARCH_COMPLETED
  -> REPORT_GENERATING
  -> REPORT_COMPLETED
  -> FAILED
```

Phase 0 不使用 LangGraph。原因是 MVP 阶段状态较少，手写 `asyncio` 状态机更透明、更易调试，也更容易观察每一步的模型输入、输出和工具调用。

## 5. Phase 1：极简 Web MVP

### 5.1 阶段目标

在 CLI 链路稳定后，用单页面 Web 应用承载核心研究流程：

```text
输入主题 -> 展示研究计划 -> 点击执行 -> 展示 Markdown 报告
```

### 5.2 包含功能

- 单页面 Web 应用。
- 用户输入研究主题。
- 后端同步或简单轮询执行研究任务。
- 页面展示 Planner 生成的研究计划。
- 用户确认后执行搜索。
- 页面展示研究执行状态。
- 页面展示最终 Markdown 报告。
- 展示引用来源列表。

### 5.3 暂不包含

- 登录。
- 多用户空间。
- 历史记录。
- 报告编辑器。
- PDF 导出。
- 复杂 SSE/WebSocket。
- 私域知识库。
- Coder Agent。
- PPT、播客、多报告风格。

### 5.4 推荐技术

前端：

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- Markdown 渲染组件

后端：

- FastAPI
- Python asyncio 状态机
- SQLite
- Pydantic
- 简单 REST API

### 5.5 为什么 Phase 1 仍然保持极简

这个阶段的目标不是做出完整 SaaS，而是验证用户是否愿意使用这个研究闭环，以及报告质量是否达到可接受水平。登录、导出、编辑、历史记录都很重要，但它们不会直接证明 Agent 工作流本身是否可靠。

## 6. Phase 2：工程化增强

### 6.1 阶段目标

把已经验证过的核心闭环扩展成稳定的工程产品。

### 6.2 新增能力

- 异步任务队列。
- 任务历史记录。
- 登录和用户系统。
- 报告编辑器。
- 报告版本管理。
- PDF / Markdown 导出。
- Coder Agent。
- Python 沙箱。
- 私域知识库和文档上传。
- PostgreSQL + pgvector。
- Agent 执行日志可视化。
- 更完整的错误重试和降级策略。

### 6.3 技术升级

- SQLite 升级为 PostgreSQL。
- 简单轮询升级为 SSE 或 WebSocket。
- 手写状态机可保留，也可以在复杂度上升后迁移 LangGraph。
- 本地日志升级为结构化数据库记录。
- 文件存储从本地升级为 S3 / MinIO / Vercel Blob。

## 7. Phase 3：产品化扩展

### 7.1 阶段目标

从“可用的研究工具”升级为“专业研究工作台”。

### 7.2 新增能力

- 多报告风格。
- PPT 生成。
- 播客脚本生成。
- 文本续写、修正、扩展、缩短。
- MCP 工具集成。
- 多人协作研究。
- 研究模板市场。
- 自定义 Agent 工作流。
- 研究知识图谱。
- 组织级权限和团队空间。

### 7.3 产品方向

Phase 3 更适合在核心链路稳定、用户需求明确、成本模型可控后推进。否则容易在基础能力尚未稳定时过早进入复杂功能堆叠。

## 8. Agent 设计方案

### 8.1 统一 Agent Card

PRD 中的 Agent 提示词不建议原样上线，而应工程化改写为统一的 Agent Card：

```text
Agent Card
- Name
- Responsibility
- Trigger
- Inputs
- Tools
- Decision Rules
- Output Schema
- Failure Handling
- Forbidden Behaviors
- Evaluation Criteria
```

Agent Card 的作用是让产品、开发、测试都能用同一套语言理解 Agent 的能力边界。

### 8.2 Planner Agent

职责：

- 接收用户研究主题。
- 判断研究主题是否需要进一步拆解。
- 生成结构化研究计划。
- 控制研究步骤数量。

输出 Schema：

```ts
interface ResearchPlan {
  locale: string;
  has_enough_context: boolean;
  thought: string;
  title: string;
  steps: ResearchStep[];
}

interface ResearchStep {
  title: string;
  description: string;
  need_search: boolean;
  step_type: "research" | "processing";
}
```

MVP 阶段 Planner 默认生成 3-5 个 `research` 步骤。`processing` 步骤可以保留字段，但 Coder Agent 暂不实现。

### 8.3 Researcher Agent

职责：

- 执行需要搜索的研究步骤。
- 生成搜索关键词。
- 调用搜索工具。
- 整理搜索结果。
- 提取可引用来源。
- 输出每一步的研究发现。

输出 Schema：

```ts
interface ResearchFinding {
  step_id: string;
  problem_statement: string;
  findings_markdown: string;
  conclusion: string;
  references: SourceReference[];
}

interface SourceReference {
  title: string;
  url: string;
  source_type: "web" | "knowledge_base" | "document";
  published_at?: string;
  retrieved_at: string;
  confidence: number;
}
```

MVP 阶段只实现 `web` 来源。`knowledge_base` 和 `document` 预留到 Phase 2。

### 8.4 Reporter Agent

职责：

- 汇总所有研究步骤结果。
- 生成结构化 Markdown 报告。
- 统一引用格式。
- 避免编造未在研究结果中出现的信息。

报告结构：

```text
# Title

## Key Points

## Overview

## Detailed Analysis

## Limitations

## Key Citations
```

MVP 阶段只支持一种通用报告风格。多风格报告放到 Phase 3。

### 8.5 Coordinator Agent

Coordinator 在完整 PRD 中非常重要，但 MVP 阶段可以弱化。

Phase 0 和 Phase 1 可先不做复杂 Coordinator，只做最小逻辑：

- 如果输入为空，提示用户重新输入。
- 如果输入明显过短，提示用户补充。
- 其他情况直接进入 Planner。

多轮澄清、意图分类、不当请求识别放到 Phase 2。

### 8.6 Coder Agent

Coder Agent 暂不进入 MVP。

Phase 2 再实现：

- Python 代码生成。
- 沙箱执行。
- 数据分析。
- 图表生成。
- 错误自动修复。

## 9. Prompt 工程化方案

### 9.1 总体原则

PRD 中的系统提示词值得借鉴，但不直接复制上线。原因是 PRD 提示词偏长，且混合了产品说明、工程约束、输出格式和测试思路。生产环境应拆成更短、更稳定、更容易评估的组件。

### 9.2 Prompt 拆分

每个 Agent 的 prompt 拆成：

```text
system prompt
developer instruction
tool instruction
output schema
few-shot examples
eval cases
```

### 9.3 Prompt 文件建议

```text
prompts/
  planner.system.md
  researcher.system.md
  reporter.system.md
  coordinator.system.md
  coder.system.md

evals/
  planner.plan_quality.yaml
  researcher.source_quality.yaml
  reporter.report_quality.yaml
  coordinator.intent.yaml
```

### 9.4 关键策略

Planner：

- 强制 JSON 输出。
- 限制步骤数。
- 每个步骤必须有明确目标。
- 默认复杂主题需要搜索。

Researcher：

- 事实性结论必须来自工具结果。
- 引用 URL 必须来自搜索或抓取结果。
- 不允许编造来源。
- 对时间敏感问题必须考虑当前日期。

Reporter：

- 只能使用 Researcher 提供的信息。
- 不添加无来源事实。
- 引用统一放到 `Key Citations`。
- 信息不足时明确说明限制。

## 10. 技术栈选择

### 10.1 Phase 0 技术栈

- Python
- asyncio
- Pydantic
- httpx
- rich
- Markdown 本地文件
- SQLite 可选

### 10.2 Phase 1 技术栈

前端：

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui

后端：

- FastAPI
- SQLite
- Pydantic
- asyncio

### 10.3 Phase 2 技术栈

- PostgreSQL
- pgvector
- Redis
- Celery / Dramatiq
- Docker 沙箱
- S3 / MinIO / Vercel Blob
- SSE / WebSocket

### 10.4 暂不在 MVP 使用 LangGraph

LangGraph 适合复杂 Agent 工作流，但 MVP 阶段优先使用手写 `asyncio` 状态机。等状态复杂度增加，例如加入多轮澄清、Coder、RAG、多工具路由、人工反馈节点后，再评估是否迁移到 LangGraph。

## 11. 模型选型策略

### 11.1 总体策略

模型选型不锁死单一供应商。MVP 阶段可以先接入 1-2 家模型，但代码层面预留统一接口：

```ts
interface LLMProvider {
  generateText(input: GenerateTextInput): Promise<GenerateTextOutput>;
  generateJson<T>(input: GenerateJsonInput): Promise<T>;
}
```

### 11.2 国内外模型并行考虑

国外模型：

- OpenAI GPT 系列：适合高质量规划、报告生成、结构化输出。
- Claude 系列：适合长文本理解和报告写作，可作为后续备选。
- Gemini 系列：适合多模态和长上下文场景，可作为后续备选。

国内模型：

- DeepSeek：适合成本敏感型推理、摘要、工具调用场景。
- Qwen / 阿里百炼：中文能力强，适合中文研究、摘要和长文本任务。
- 智谱 GLM：可作为国内模型备选。

### 11.3 Agent 模型分配

| Agent | 模型策略 |
|---|---|
| Coordinator | 低成本快模型 |
| Planner | 中高质量模型 |
| Researcher | 快模型 + 工具调用能力强的模型 |
| Reporter | 高质量长文模型 |
| Coder | 代码和推理能力较强的模型 |

### 11.4 MVP 默认策略

MVP 阶段建议：

- Planner 使用质量更高的模型，保证计划可执行。
- Researcher 使用成本较低的模型，控制多步骤调用成本。
- Reporter 使用质量较高的模型，保证最终报告体验。
- 所有模型调用走统一接口，后续方便切换供应商。

## 12. 成本估算与预算控制

### 12.1 单次研究成本估算

粗略估算：

| 研究类型 | 预估成本 |
|---|---|
| 轻量研究 | 0.05 - 0.15 美元 |
| 标准研究 | 0.2 - 0.8 美元 |
| 深度研究 | 1 - 3+ 美元 |

实际成本取决于：

- 研究步骤数量。
- 搜索调用次数。
- 抓取页面数量。
- 输入上下文长度。
- Reporter 输出长度。
- 失败重试次数。
- 使用的模型价格。

### 12.2 MVP 硬性预算限制

每次研究任务必须设置：

```text
max_steps
max_search_calls
max_crawl_pages
max_tokens_budget
max_retries
```

建议默认值：

```text
max_steps = 3
max_search_calls = 6
max_crawl_pages = 6
max_tokens_budget = 80000
max_retries = 2
```

### 12.3 成本记录

每次任务记录：

- 模型名称。
- 输入 token。
- 输出 token。
- 模型费用。
- 搜索 API 调用次数。
- 抓取页面数。
- 总耗时。
- 失败和重试次数。

### 12.4 成本优化策略

- Coordinator 和摘要任务使用低成本模型。
- Planner 和 Reporter 使用高质量模型。
- 对搜索结果先做截断和去重，再进入模型。
- 避免把完整网页无脑塞进上下文。
- 对相同 URL 的抓取结果做缓存。
- 失败重试时优先修复输出格式，必要时再升级模型。

## 13. 数据结构与接口设计

### 13.1 Phase 0 本地数据

Phase 0 可以用本地 JSON / Markdown 文件保存：

```text
runs/
  run_20260603_001/
    input.json
    plan.json
    findings.json
    report.md
    usage.json
    logs.txt
```

### 13.2 Phase 1 SQLite 表

建议最小表结构：

```text
research_tasks
research_steps
research_findings
sources
reports
agent_runs
```

### 13.3 核心 API

Phase 1 最小 API：

```http
POST /api/research/plan
POST /api/research/run
GET /api/research/:id
```

后续 Phase 2 扩展：

```http
POST /api/research-tasks
GET /api/research-tasks/:id
POST /api/research-tasks/:id/confirm-plan
GET /api/research-tasks/:id/events
GET /api/research-tasks/:id/report
POST /api/reports/:id/rewrite
POST /api/reports/:id/export
POST /api/knowledge-documents
```

### 13.4 事件类型

后续支持实时状态时，可使用：

```ts
type ResearchEvent =
  | { type: "planner.started" }
  | { type: "planner.completed"; plan: ResearchPlan }
  | { type: "step.started"; step_id: string }
  | { type: "tool.called"; tool_name: string }
  | { type: "step.completed"; step_id: string }
  | { type: "report.started" }
  | { type: "report.completed"; report_id: string }
  | { type: "error"; message: string };
```

## 14. 测试与评估方案

### 14.1 测试原则

AI 产品测试不是只看固定输出是否完全一致，而是看输出是否满足结构、约束、质量和安全标准。

测试分为：

- 单 Agent 测试。
- 工具调用测试。
- Schema 测试。
- 端到端测试。
- 成本和性能测试。
- 人工报告质量评估。

### 14.2 Planner 测试

测试点：

- 是否输出合法 JSON。
- 是否生成 3-5 个步骤。
- 步骤是否覆盖主题关键维度。
- 每个步骤是否足够具体。
- 是否正确标记 `need_search`。

样例：

```yaml
- input: "分析 2026 年中国 AI Agent 市场趋势"
  expected:
    min_steps: 3
    max_steps: 5
    should_cover:
      - 市场规模
      - 主要玩家
      - 技术趋势
      - 商业化挑战
```

### 14.3 Researcher 测试

测试点：

- 是否调用搜索工具。
- 是否返回真实 URL。
- 是否去除明显重复来源。
- 是否记录标题和来源。
- 是否避免使用无来源事实。

### 14.4 Reporter 测试

测试点：

- 是否包含固定报告结构。
- 是否包含 Key Points。
- 是否包含引用列表。
- 是否只使用 Researcher 结果。
- 是否明确说明信息不足。

### 14.5 E2E 测试

MVP 至少准备 20 个端到端主题：

- 技术趋势类。
- 市场分析类。
- 竞品分析类。
- 学术综述类。
- 投资分析类。

每个 E2E case 检查：

- 能否完成。
- 耗时。
- 成本。
- 引用数量。
- 报告结构。
- 人工评分。

### 14.6 性能指标

建议指标：

- Planner 响应小于 10 秒。
- 单个搜索步骤小于 2 分钟。
- CLI 标准研究小于 15 分钟。
- Web MVP 标准研究小于 30 分钟。
- 任务失败率低于 10%。
- 引用有效率高于 90%。

## 15. 团队角色分工

### 15.1 产品经理

负责：

- Agent 用户故事。
- 能力边界定义。
- 用户旅程。
- 人工反馈节点。
- 报告结构和风格。
- 验收标准。

### 15.2 AI / Prompt Engineer

负责：

- Agent Card。
- Prompt Template。
- Output Schema。
- Few-shot Examples。
- Eval Spec。
- Prompt 版本管理。
- 模型输出稳定性优化。

### 15.3 后端开发

负责：

- Python CLI 原型。
- FastAPI 服务。
- 状态机。
- 搜索和抓取工具。
- 模型接口。
- SQLite / PostgreSQL。
- 任务日志和成本统计。

### 15.4 前端开发

负责：

- 单页面 Web MVP。
- 研究主题输入。
- 计划展示。
- 执行状态展示。
- Markdown 报告展示。
- 后续报告编辑器。

### 15.5 测试团队

负责：

- Agent eval case。
- E2E case。
- 引用真实性测试。
- Schema 合法性测试。
- 成本和性能测试。
- 异常降级测试。

## 16. 风险与降级策略

### 16.1 MVP 范围风险

风险：功能范围过大，导致核心闭环迟迟无法跑通。

策略：

- Phase 0 只做 CLI。
- Phase 1 只做单页面 Web。
- 登录、导出、编辑、RAG、PPT、播客全部延后。

### 16.2 模型输出不稳定

风险：Planner 输出非法 JSON，Reporter 编造信息。

策略：

- 使用结构化输出。
- 加入 schema 校验。
- 失败后自动修复。
- 仍失败则记录错误并停止任务。

### 16.3 搜索质量不足

风险：搜索结果不相关、来源低质量、引用不可用。

策略：

- 多关键词搜索。
- 来源去重。
- 优先可信来源。
- 记录每个来源 confidence。
- 搜索不足时在报告中说明限制。

### 16.4 成本失控

风险：深度研究步骤过多，模型上下文和搜索 API 成本快速上升。

策略：

- 设置 token budget。
- 限制搜索次数。
- 限制抓取页面数。
- 默认低成本模型处理摘要任务。
- 记录每次任务费用。

### 16.5 代码执行风险

风险：Coder Agent 执行危险代码或消耗过多资源。

策略：

- Coder 不进入 MVP。
- Phase 2 使用 Docker 沙箱。
- 限制 CPU、内存、执行时间和文件权限。

## 17. 验收标准

### 17.1 Phase 0 验收标准

- 可以通过 CLI 输入研究主题。
- Planner 输出合法研究计划。
- Researcher 至少完成 3 个搜索步骤。
- Reporter 生成 Markdown 报告。
- 报告包含 Key Points、Detailed Analysis、Key Citations。
- 本地保存报告和运行日志。
- 记录 token、耗时和工具调用次数。
- 至少通过 10 个 CLI E2E 测试主题。

### 17.2 Phase 1 验收标准

- 可以在单页面 Web 输入主题。
- 页面展示研究计划。
- 用户可以确认并执行研究。
- 页面展示最终 Markdown 报告。
- 页面展示引用来源。
- 无登录、无导出、无编辑也可以接受。
- 至少通过 20 个 E2E 测试主题。

### 17.3 Phase 2 验收标准

- 支持任务历史记录。
- 支持报告编辑。
- 支持导出。
- 支持 Coder Agent。
- 支持私域知识库。
- 支持异步任务。
- 支持 Agent 日志查看。

### 17.4 Phase 3 验收标准

- 支持多报告风格。
- 支持 PPT 和播客脚本。
- 支持团队协作。
- 支持自定义工作流。
- 支持模板市场或模板管理。

## 18. 默认假设

- 当前目标是尽快做出高质量可验证产品，不是一开始做完整 SaaS。
- 先验证 Agent 闭环，再完善产品体验。
- Phase 0 和 Phase 1 不使用 LangGraph。
- Phase 0 和 Phase 1 使用 SQLite 或本地文件，不使用 PostgreSQL。
- PRD 中的 Agent 提示词作为高质量参考，不直接复制上线。
- 国内外模型都可以考虑，代码层面预留统一模型接口。
- MVP 不做登录、导出、编辑、RAG、PPT、播客。
- 成本控制从第一天开始记录。
- 所有关键 Agent 输出都应尽量结构化。
- 报告中的事实性内容必须能追踪到搜索结果或输入上下文。
