# DeepFlow — AI 深度研究平台

输入一个研究主题，多 Agent 协作自动完成 **资料收集 → 分析 → 报告撰写**，5 分钟产出带 50+ 真实引用的结构化研究报告。

## 核心能力

- **多 Agent 协作**：Coordinator（意图分析）→ Planner（计划生成）→ Researcher（联网搜索）→ Coder（数据分析）→ Reporter（报告撰写）
- **实时搜索**：自动检索 + 网页抓取，所有引用来自真实来源
- **代码执行**：安全沙箱运行 Python（numpy/pandas/matplotlib），自动计算和可视化
- **6 种报告风格**：通用 / 学术 / 科普 / 新闻 / 社交媒体 / 投资分析
- **成果物生成**：播客脚本（双人对话）、PPT 幻灯片
- **文本工具**：润色 / 扩展 / 精简

## 快速开始

### 前提条件

- Python 3.12+
- DeepSeek API Key（[platform.deepseek.com](https://platform.deepseek.com)）
- Tavily API Key（[tavily.com](https://tavily.com)，免费 1000 credits/月）

### 安装

```bash
git clone https://github.com/ZackZhang-AI/DeepFlow.git
cd DeepFlow

# 安装依赖（国内使用阿里云镜像）
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```

### 配置

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key：
#   DEEPSEEK_API_KEY=sk-xxx
#   TAVILY_API_KEY=tvly-xxx
```

### CLI 运行

```bash
# 单次研究
python -m cli.main "分析 2026 年 AI Agent 市场发展趋势"

# 交互模式
python -m cli.main --interactive

# 跳过计划确认
python -m cli.main "量子计算进展" -y --max-steps 3

# 评测 Planner
python -m evals.runner --agent planner
```

### Web 运行

```bash
# 终端 1：启动后端
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：启动前端
cd frontend && npm install && npm run dev

# 浏览器打开 http://localhost:3000
```

## 研究流程

```
用户输入主题 → Coordinator(意图分类) → Planner(生成3-5步计划)
                                              ↓ 用户确认
        Reporter(6段结构报告) ← Researcher×N(搜索+抓取+总结) + Coder(沙箱执行)
              ↓
    Artifact Agents: 播客脚本 / PPT幻灯片 / 文本润色扩展精简
```

## 成本

| 研究类型 | 步骤 | 时间 | 费用 |
|---------|------|------|------|
| 快速 | 2-3 步 | ~3 分钟 | <¥0.30 |
| 标准 | 4-5 步 | ~8 分钟 | ~¥0.80 |
| 深度 | 5-8 步 | ~15 分钟 | ~¥1.50 |

使用 DeepSeek V4-Pro，单次研究约 ¥0.80-1.10（≈$0.12-0.16）。

## 技术栈

| 层 | 选择 |
|---|------|
| AI 模型 | DeepSeek V4-Pro / V4-Flash |
| 后端 | Python FastAPI + SQLite |
| 前端 | Next.js 16 + React + TypeScript + Tailwind CSS |
| 搜索 | Tavily Search API |
| 沙箱 | 子进程隔离（生产环境可选 Docker） |
| 编排 | 自研 asyncio 状态机 |

## 项目结构

```
DeepFlow/
├── cli/                      # Agent 引擎（代码可脱离后端运行）
│   ├── agents/               # Coordinator / Planner / Researcher / Coder / Reporter
│   │   └── artifacts/        # 播客 / PPT / 文本工具 Agent
│   ├── tools/                # 搜索 / 抓取 / 沙箱
│   ├── main.py               # CLI 入口
│   └── state_machine.py      # 研究流程状态机
├── backend/                  # FastAPI 后端
│   └── app/
│       ├── api/routes/       # research / events(SSE) / report / artifacts
│       ├── core/             # SQLite 数据库 / SSE 事件管理
│       └── services/         # 后台研究任务执行
├── frontend/                 # Next.js Web 工作台
│   ├── app/                  # 主页 + 历史页
│   └── components/           # ReportView / Timeline / StyleSelector / ArtifactTools
├── prompts/                  # Agent 提示词（版本化 @v1, @v2）
│   └── artifacts/            # 播客 / PPT / 文本工具 Prompt
├── evals/                    # Eval Cases + Runner
└── output/                   # 研究报告输出
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/research-tasks` | 创建研究任务 |
| GET | `/api/research-tasks/{id}` | 查询任务状态 |
| GET | `/api/research-tasks` | 历史任务列表 |
| GET | `/api/research-tasks/{id}/events` | SSE 实时进度流 |
| GET | `/api/reports/{id}` | 获取报告 |
| GET | `/api/reports/{id}/download` | 下载 Markdown |
| POST | `/api/artifacts/restyle` | 切换报告风格 |
| POST | `/api/artifacts/podcast` | 生成播客脚本 |
| POST | `/api/artifacts/ppt` | 生成 PPT Markdown |
| POST | `/api/artifacts/prose/improve` | 文本润色 |
| POST | `/api/artifacts/prose/expand` | 文本扩展 |
| POST | `/api/artifacts/prose/shorten` | 文本精简 |

## License

MIT
