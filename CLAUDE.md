# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DeepFlow is a multi-agent deep research platform. Users input a topic → Coordinator classifies intent → Planner generates a research plan → Researcher executes web searches → Coder runs data processing (optional) → Reporter synthesizes a structured, citation-backed report. The report can be regenerated in 6 styles (general, academic, popular_science, news, social_media, strategic_investment) and converted to podcast scripts or PPT slides.

## Architecture

```
User Input → [Coordinator] → [Planner] → [Human Confirm]
                                              ↓
              [Reporter] ← [Researcher × N steps] + [Coder for processing steps]
                  ↓
         [Artifact Agents: Podcast, PPT, Prose tools]
```

**Agent data flow**: Each Agent reads typed Pydantic models from `cli/models.py`. The state machine (`cli/state_machine.py`) orchestrates: Planner output (ResearchPlan) → Researcher/Coder output (ResearchFinding) → Reporter output (Markdown string). All backend services reuse the exact same Agent code under `cli/agents/`.

**LLM abstraction** (`cli/agents/base.py`): `LLMProvider` wraps the OpenAI-compatible SDK. `generate_text()` returns raw text; `generate_json()` uses a retry loop (max 2 retries) to validate against a Pydantic model. Model routing: `deepseek-*` → DeepSeek API, `qwen-*` → DashScope API. Configuration lives in `cli/config.py` (loaded from `.env`).

**Prompt system** (`prompts/`): Each Agent has versioned prompt files named `{agent}@v{version}.md` with YAML frontmatter (agent, version, model, temperature, max_tokens). `prompt_loader.py` resolves the file and substitutes `{{ CURRENT_TIME }}`. Artifact prompts live in subdirectory `prompts/artifacts/`.

**Backend** (`backend/`): FastAPI app with 4 route modules: `research.py` (CRUD), `events.py` (SSE streaming), `report.py` (fetch + download), `artifacts.py` (podcast/PPT/prose/restyle). Research tasks run in-process via `BackgroundTasks` (not Celery for MVP). `EventManager` (`core/events.py`) is an asyncio.Queue per task; SSE consumers drain from the queue. SQLite with WAL mode (`core/db.py`), no threading locks since everything runs in a single asyncio event loop.

**Frontend** (`frontend/`): Next.js 16 App Router. Single-page research workspace (`app/page.tsx`) with SSE-driven progress updates. History page (`app/history/`). Four components: `ReportView` (edit/preview/export), `Timeline` (agent execution log), `StyleSelector` (6 report style buttons), `ArtifactTools` (podcast/PPT generation).

**Sandbox** (`cli/tools/sandbox.py`): Subprocess-based Python execution with 13 forbidden-pattern regex checks and an allowed-import whitelist. Docker mode supported as fallback. Coder Agent (`cli/agents/coder.py`) routes `need_search=false` steps here.

## Common Commands

```bash
# Install dependencies (use Aliyun mirror on Windows)
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# CLI: single research (skip plan confirmation with -y)
python -m cli.main "你的研究主题"
python -m cli.main "topic" -y --max-steps 3
python -m cli.main --interactive

# Backend (port 8000)
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (port 3000)
cd frontend && npm run dev

# Eval runner
python -m evals.runner --agent planner
python -m evals.runner --agent all
```

## Key Conventions

- **`need_search` boolean on ResearchStep** determines routing: `true` → Researcher (web search + crawl + summarize), `false` → Coder (write Python → sandbox execute → analyze). The state machine and backend service both honor this.
- **All Python code runs from the project root** (`DeepFlow/`). Import paths assume root is on `sys.path` — both `cli/` and `backend/` modules reference each other via `from cli.xxx import yyy`.
- **`.env` file is required** at project root. Template at `.env.example`. Keys needed: `DEEPSEEK_API_KEY`, `TAVILY_API_KEY`. Optional: `DASHSCOPE_API_KEY` (Reporter fallback), `SERPAPI_API_KEY` (search fallback).
- **Model assignment per Agent** is configured via env vars: `PLANNER_MODEL`, `RESEARCHER_MODEL`, `REPORTER_MODEL`, `REPORTER_FALLBACK_MODEL`. Defaults to `deepseek-chat`.
- **Prompt versioning**: load with `load_prompt("reporter", version=2)`. The loader appends `@v{version}` to the filename and looks in `prompts/`. Artifact prompts use subdirectory syntax: `load_prompt("artifacts/podcast_script")`.
- **Eval cases** are YAML files in `evals/cases/{agent}.yaml`. Each case has `input` and `expected` (assertion rules). The runner calls the real Agent and checks schema constraints.
- **SSE event lifecycle**: `coordinator.started` → `planner.completed` → `research.started` → (N × `step.started`/`step.completed`) → `report.started` → `report.completed`. Terminal event: `error.fatal`. The `EventManager` stream auto-closes after terminal events.
- **Research outputs** saved to `output/{run_id}/` with `record.json` (full metadata), `report.md`, and `summary.txt`.
