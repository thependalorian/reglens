# RegLens — Web Workspace

Next.js + CopilotKit v2 frontend for [RegLens](../reglens), an adaptive
regulatory sludge-detection agent. One agent-driven workspace: a chat beside a
shared-state canvas the agent updates live, plus document management for the
ingest pipeline.

Self-hosted: the CopilotKit runtime brokers to the RegLens FastAPI backend's
AG-UI endpoint. No managed Intelligence service — no corpus or conversation
data leaves your infrastructure.

## Run

The backend must be running first (see `../reglens`):

```bash
# Terminal 1 — backend (FastAPI on :8058)
cd ../reglens && uvicorn agent.api:app --port 8058

# Terminal 2 — this app (Next.js on :3000)
npm install
npm run dev
```

Open http://localhost:3000.

## Configuration

`.env` (gitignored — never commit secrets):

```
AGENT_URL=http://localhost:8058        # backend base URL; runtime appends /agui
BACKEND_URL=http://localhost:8058      # REST proxy target (documents, corpus, health)
REGLENS_API_TOKEN=                     # server-side bearer; empty = backend dev mode
```

## What you can do

- **Chat** an analysis request. The agent triages, retrieves, detects sludge,
  validates every citation, and pauses for your review.
- **Review** findings inline: verbatim citations, evidence-based confidence,
  and coverage disclosure. Approve, reject, or refine (optionally escalating
  to an exhaustive full-corpus sweep).
- **Manage documents**: upload files into the ingest pipeline (parsed and
  embedded in the background), see status and chunk counts, and remove them.

## Structure

```
src/
  app/
    page.tsx                         # the single workspace
    layout.tsx                       # CopilotKit provider (self-hosted)
    api/copilotkit/[[...slug]]/      # runtime -> LangGraphHttpAgent -> backend /agui
    api/backend/[...path]/           # authenticated REST proxy
  components/
    reglens/                         # canvas, stepper, findings, coverage, report, documents
    example-layout/                  # chat + canvas split, Chat/App toggle
  lib/reglens/                       # types (mirror backend models), copy, logger
```

All agent logic and Python live in [`../reglens`](../reglens). This app is UI only.
