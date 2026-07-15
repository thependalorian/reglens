# RegLens web workspace (CopilotKit v2 + AG-UI)

Next.js frontend for **RegLens**, a regulatory sludge-detection agent. This
app is UI only — all agent logic and Python live in the separate backend at
`../reglens` (FastAPI + LangGraph + Pydantic AI + Neon). Do not add Python
here.

## How it connects

```
Browser (this app)
  CopilotKit v2 provider (runtimeUrl=/api/copilotkit, agent "default")
        |
  src/app/api/copilotkit/[[...slug]]/route.ts
    CopilotRuntime + LangGraphHttpAgent({ url: AGENT_URL + "/agui" })
    InMemoryAgentRunner  (self-hosted — NO managed Intelligence)
        |  AG-UI protocol (SSE)
  ../reglens  FastAPI  /agui  (ag-ui-langgraph over the LangGraph workflow)
```

The backend's `SludgeWorkflowState` streams over AG-UI; the UI reads it with
`useAgent().state` (shared state) and renders it live. Human review is a
LangGraph `interrupt()` surfaced via `useInterrupt`.

`src/app/api/backend/[...path]/route.ts` is a thin authenticated proxy to the
backend's REST endpoints (documents, corpus, health) so the API token stays
server-side.

## Layout

- One page (`src/app/page.tsx`): a chat beside a shared-state canvas.
- `src/components/reglens/canvas.tsx` — two tabs:
  - **Analysis**: `workflow-stepper`, `coverage-meter`, `finding-card`, `report-view`.
  - **Documents**: `document-manager` — upload/list/delete the ingest pipeline.
- `findings-review-panel` — the HITL interrupt UI (approve / reject / refine).
- `src/lib/reglens/` — `types` (mirror the backend models), `copy` (all
  user-facing strings; no hardcoded text on pages), `logger`.
- `src/components/example-layout/` — the chat/canvas split + Chat/App toggle.

## Rules

- No emojis in copy, code, or comments.
- All user-facing strings live in `src/lib/reglens/copy.ts`.
- No raw `console.*` in components — use `src/lib/reglens/logger.ts`.
- Keep this app Python-free; the agent is `../reglens`.

## Env (`.env`, gitignored)

```
AGENT_URL=http://localhost:8058        # backend base; runtime appends /agui
BACKEND_URL=http://localhost:8058      # REST proxy target
REGLENS_API_TOKEN=                     # server-side bearer (empty = backend dev mode)
```

## Dev

```bash
npm install
npm run dev        # next dev on :3000 (backend must be running on :8058)
npm run build
```
