# DeepFlow Demo Launch Checklist

Use this checklist for the zero-cost Vercel Hobby + Render Free showcase.

## Deployment Records

Fill these in after creating the services:

| Item | Value |
| --- | --- |
| GitHub branch | `codex/deepflow-prd-implementation` |
| Render backend URL | `https://<render-backend-domain>` |
| Vercel frontend URL | `https://<vercel-domain>` |
| Demo username | `<DEMO_USERNAME>` |
| Demo password storage | Store outside GitHub, e.g. password manager |
| Demo video URL | `https://<video-url>` |

## Render Backend

Create a Render Web Service from `ZackZhang-AI/DeepFlow`.

- Root Directory: repository root
- Build Command:
  ```bash
  pip install -r requirements.txt && pip install -r backend/requirements.txt
  ```
- Start Command:
  ```bash
  python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
  ```
- Storage: Render Free ephemeral filesystem. Demo seed data is rebuilt at startup.

Required environment variables:

```env
ALLOW_PUBLIC_REGISTRATION=false
DEMO_SEED_ENABLED=true
DEMO_SHARE_TOKEN=deepflow-showcase
DEMO_USERNAME=<demo-user>
DEMO_PASSWORD=<strong-password>
DISABLE_SANDBOX_TOOL=true
CORS_ORIGINS=https://<vercel-domain>
DEEPSEEK_API_KEY=<optional-secret-for-private-live-demo>
TAVILY_API_KEY=<optional-secret-for-private-live-demo>
RATE_LIMIT_WINDOW_SECONDS=3600
RESEARCH_TASK_RATE_LIMIT_PER_HOUR=3
READINESS_PROBE_RATE_LIMIT_PER_HOUR=6
TOOL_TEST_RATE_LIMIT_PER_HOUR=10
KNOWLEDGE_WRITE_RATE_LIMIT_PER_HOUR=10
ARTIFACT_RATE_LIMIT_PER_HOUR=10
KNOWLEDGE_UPLOAD_MAX_BYTES=5242880
```

Backend acceptance checks:

- `GET https://<render-backend-domain>/api/health` returns `{"status":"ok","version":"0.1.0"}`.
- Demo account can log in.
- Public registration returns HTTP 403.
- Python sandbox tool test returns HTTP 403 when disabled.
- The public sample returns after a restart because seed initialization is idempotent.
- User-created tasks and uploads may be lost after a restart, redeploy, or instance recycle.

## Vercel Frontend

Create a Vercel project from the same GitHub repository.

- Root Directory: `frontend`
- Build Command: `npm run build`
- Environment:
  ```env
  NEXT_PUBLIC_API_URL=https://<render-backend-domain>
  NEXT_PUBLIC_DEMO_SHARE_TOKEN=deepflow-showcase
  ```

Frontend acceptance checks:

- `/login` opens from the Vercel URL.
- Demo account logs in successfully.
- Browser devtools show no CORS failures.
- Creating a research task shows progress or a readable error message.
- `/shared/deepflow-showcase` renders the seeded report without login.
- `/history` shows seeded private demo assets after login; visitor-created data is ephemeral.

## Demo Seed Content

Recommended research task:

```text
2026 年 AI Agent 产品形态与商业化趋势简析
```

Recommended knowledge document:

```markdown
# DeepFlow Demo Knowledge Note

DeepFlow is a multi-agent research workspace with planning, search, private knowledge retrieval, code execution safeguards, report generation, and artifact export. This note exists to demonstrate private knowledge search in the public demo.
```

Standard demo path:

1. Open `/shared/deepflow-showcase` without logging in to show the fixed, zero-cost report.
2. Log in with the private demo account.
3. Open the seeded RAG sample and locate a `kb://` source chunk.
4. Only when private Provider secrets are configured, create the recommended live research task.
5. Confirm the plan, inspect Agent Trace, review the report, and export an artifact.

Screenshots to capture:

- Workspace with a task in progress or completed.
- Agent Trace / timeline.
- Final report or exported artifact panel.

## README Patch After URLs Exist

Add this block near the top of `README.md` after deployment:

```markdown
## Online Demo

- Demo: https://<vercel-domain>
- Demo account: `<DEMO_USERNAME>`
- Demo video: https://<video-url>

The public demo disables open registration and Python sandbox execution to keep API costs and execution risk controlled.
```

## Resume Bullets

- Built DeepFlow, a full-stack multi-agent deep research platform using FastAPI, Next.js, SQLite, and OpenAI-compatible LLM providers.
- Implemented an Agent workflow covering planning, web search, private RAG retrieval, code-tool safeguards, SSE progress tracing, report generation, and artifact export.
- Added demo-safe deployment controls including rebuildable seed data, closed registration, demo account bootstrap, rate limits, upload limits, CORS configuration, and sandbox disablement.
- Prepared the project for Vercel + Render deployment with documented environment variables, validation tests, and public-demo operating boundaries.

## Interview Talk Track

1. Problem: deep research workflows are fragmented across search, notes, analysis, and report writing.
2. Architecture: FastAPI backend, Next.js frontend, SQLite persistence, shared CLI Agent layer, SSE event stream.
3. Agent flow: Coordinator/Planner creates a plan; Researcher/Coder collect findings; Reporter synthesizes a citation-backed Markdown report.
4. RAG: user documents are parsed, chunked, embedded, stored in SQLite, and retrieved with vector + keyword scoring.
5. Safety: the public demo closes registration, limits costly endpoints, protects live readiness probes, and disables sandbox execution.
6. Boundary: Render Free storage is ephemeral; seeded examples recover automatically, while real user history is not guaranteed.
