# RegLens

Regulatory sludge-detection agent for central-bank supervisors. RegLens reads
an ingested corpus of regulatory instruments and surfaces **policy sludge** —
overlapping, conflicting, or accumulated obligations — with every finding
pinned to a mechanically verified verbatim citation, an honest coverage
disclosure, and human review before anything is published.

This is a monorepo with two independently runnable projects.

## Layout

| Path | What it is | Stack |
|---|---|---|
| [`reglens/`](reglens/) | Backend agent + API | FastAPI, LangGraph, Pydantic AI, Neon Postgres (pgvector) |
| [`reglens-frontend/`](reglens-frontend/) | Web workspace | Next.js 16, React 19, CopilotKit v2, AG-UI, Tailwind v4 |

The frontend is UI only; all agent logic and Python live in `reglens/`. They
communicate over the AG-UI protocol: the backend exposes `/agui`, the frontend
proxies to it through `/api/copilotkit`.

## How it works

```
Browser (reglens-frontend)
  CopilotKit v2 provider  ->  /api/copilotkit  ->  LangGraphHttpAgent
        |  AG-UI (SSE)
  reglens  FastAPI  /agui  ->  LangGraph workflow
        triage -> discover -> retrieve -> detect -> validate -> HITL review -> report
```

- **Factuality first**: every citation's `verbatim_quote` is substring-verified
  against the corpus before it can reach a report; confidence is recomputed
  from verified evidence, never the model's self-report.
- **Human-in-the-loop**: findings pause at a LangGraph `interrupt()` for expert
  approve / refine / reject, surfaced in the UI via `useInterrupt`.
- **Coverage honesty**: each run discloses exactly which documents were examined
  and what fraction of the corpus that represents.

## Running locally

Backend (from `reglens/`):

```bash
cd reglens
source .venv/bin/activate
uvicorn agent.api:app --host 0.0.0.0 --port 8058 --reload
```

Frontend (from `reglens-frontend/`, in a second terminal):

```bash
cd reglens-frontend
npm install
npm run dev        # http://localhost:3000 (expects the backend on :8058)
```

Each project has its own `README`, `CLAUDE.md`, and `.env.example` — see those
for configuration details.
