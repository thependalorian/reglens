# RegLens — Regulatory Sludge Intelligence Agent

Adaptive agentic AI for regulatory sludge detection, pre-rulemaking
policy checks, and cross-border regulatory gap analysis.

Built for the CDIR Global 'Agentic Regulator' Hackathon 2026.
Designed from lived experience in the Namibian fintech and SADC
payment infrastructure sector — and fully agnostic of jurisdiction,
regulator, and domain.

## What it does

Drop in any regulatory documents. RegLens discovers the regulatory
context from the documents themselves and provides three capabilities:

1. **Sludge Detection** — find overlapping, inconsistent, outdated obligations
2. **Pre-rulemaking Check** — compare a draft against the existing corpus before publication
3. **Cross-border Comparison** — gap analysis and harmonisation score between two frameworks

No hardcoded jurisdictions. No hardcoded domains. Fully adaptive.

## Factuality and Trust

RegLens is built for regulators, so "how do we know the agent is not
making this up" is answered by architecture, not by promises:

- **Verbatim citations, mechanically verified.** Every finding must quote
  the corpus exactly, pinned to the source chunk (`chunk_uid`) and
  document. Before the LLM validator runs, every quote is
  substring-matched against the retrieved corpus text — a quote that is
  not in the corpus is treated as fabrication and fails validation.
- **Evidence-based confidence.** A finding's confidence score is computed
  as verified citations / total citations (capped by the model's own
  self-assessment). Zero citations = zero confidence. The model cannot
  award itself credibility.
- **Intent triage.** A routing gate classifies every request before any
  retrieval happens. Greetings, small talk, off-topic requests, and
  unanswerable asks get a short direct reply and never trigger analysis.
- **Coverage disclosure.** Default analysis retrieves iteratively (the
  detector must search from at least three angles), and every report
  opens with a Scope & Coverage section stating exactly which documents
  were examined out of the full corpus. The system never claims to have
  read what it did not read.
- **Exhaustive mode.** `analyze --exhaustive <query>` sweeps every
  document in the corpus (one obligation-extraction call per document,
  then cross-document synthesis) for pre-submission audits where
  completeness matters more than speed.
- **References.** Every report ends with a References section listing
  each cited document and the provisions cited from it.
- **Personas with professional standards.** Each of the five agents has
  a defined role, background, and goal — the detector "never asserts
  what it cannot quote"; the validator is an adversarial fact-checker
  whose goal is zero fabricated citations reaching a regulator.
- **Human-in-the-loop.** No sludge finding is published without expert
  approval, and approvals survive API restarts (Postgres-checkpointed
  workflow state).

## Corpus Examples

Ingest any of these (or any combination):

**SADC / African:**

```
Bank of Namibia Payment System Determinations
NAMFISA Non-Bank Financial Institutions circulars
South African NPS Act + SARB Payment System Regulations
FATF Recommendations + SADC member Mutual Evaluation Reports
SADC Payment System Oversight Framework
ESAAMLG AML/CFT Standards
COMESA Cross-border Payment Guidelines
African Development Bank Financial Sector Guidelines
```

**Global:**

```
FCA Handbook sections
EMIR / MiFIR regulations
Basel III/IV framework documents
BIS CPMI payment system standards
FATF 40 Recommendations
Any national central bank circulars
```

## Example Queries

**Sludge Detection:**

```
analyze Find horizontal sludge in AML/CFT reporting requirements
analyze Identify vertical accumulation in payment system regulations
analyze Where do SADC member state AML frameworks diverge from FATF standards
analyze --exhaustive Find every overlapping obligation across the corpus
```

**Pre-rulemaking Check:**

```
precheck E-Money Interoperability Determination Draft 2026
precheck AML/CFT Amendment Regulations
precheck New Fintech Licensing Framework
```

**Cross-border Comparison:**

```
compare  (interactive — prompts for two framework labels and topic)
Example inputs:
  Framework A: "Bank of Namibia AML Framework"   Filter A body: "BoN"
  Framework B: "FATF Recommendations"            Filter B body: "FATF"
  Topic: "customer due diligence and beneficial ownership"
```

## Quick Start

```bash
# 1. Setup
git clone <repo> && cd reglens
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL (Neon), LLM_API_KEY

# 2. Database (Neon Postgres + pgvector)
psql "$DATABASE_URL" -f sql/schema.sql

# 3. Ingest documents (any regulatory PDFs/DOCX/TXT/MD)
# Re-run safe: files already ingested (same content hash) are skipped;
# changed files supersede their older version — no duplicates.
python -m ingestion.ingest --path ./data --recursive

# 4. Start API
uvicorn agent.api:app --host 0.0.0.0 --port 8058 --reload

# 5. CLI
python cli.py --port 8058
```

**Port 8058 already in use?** A stale server from a previous run is
holding it — clear it before restarting:

```bash
lsof -ti :8058 | xargs kill -9 2>/dev/null; echo "port clear"
```

## Document Parsing

Ingestion parses documents through a quality hierarchy
(`ingestion/parser.py`):

1. **LlamaParse** (cloud, VLM-based) — used when `LLAMA_CLOUD_API_KEY` is set.
   Best for scanned PDFs and complex nested tables.
2. **Docling** (local AI/ML layout model) — default. Preserves tables and
   multi-column layouts in FATF/Basel/central-bank PDFs. No API key, no
   corpus data leaving the environment — a meaningful compliance property
   for central bank deployments.
3. **Plain text** — `.txt` / `.md` read directly.

Run `parsers` in the CLI to see what is available in your environment.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (includes parser status) |
| GET | `/api/reglens/corpus` | Corpus map — what is ingested |
| GET | `/api/reglens/usecases` | All use cases and tracks |
| POST | `/api/reglens/analyze` | Sludge detection (SSE stream) |
| POST | `/api/reglens/precheck` | Pre-rulemaking check (SSE stream) |
| POST | `/api/reglens/compare` | Cross-border comparison (SSE stream) |
| POST | `/api/reglens/approve` | HITL approval/rejection |
| GET | `/api/reglens/findings/{session_id}` | Findings for review |
| GET | `/api/reglens/session/{session_id}/report` | Final report |
| GET | `/api/reglens/documents` | List the ingest pipeline (per-document status + chunk counts) |
| POST | `/api/reglens/documents` | Upload a document (async ingest; returns `processing`) |
| DELETE | `/api/reglens/documents/{document_uid}` | Remove a document and its chunks |
| POST/GET | `/agui` | AG-UI protocol endpoint for the CopilotKit web UI |

## Web UI (CopilotKit + AG-UI)

`reglens-frontend/` is a Next.js app (CopilotKit v2, self-hosted — no managed
Intelligence, no corpus data leaves local infra) that presents one
agent-driven workspace: a chat beside a shared-state canvas the agent updates
live. The canvas has two tabs:

- **Analysis** — the workflow stepper (triage → discover → retrieve → detect
  → validate → review → report), coverage meter, findings with verbatim
  citations, and the rendered report. Expert review happens inline in chat as
  a Human-in-the-Loop interrupt (approve / reject / refine + exhaustive toggle).
- **Documents** — manage the ingest pipeline: upload files (parsed and embedded
  in the background, shown as `processing → active`), see chunk counts and
  regulatory metadata, and remove documents.

```bash
# Terminal 1 — backend
uvicorn agent.api:app --port 8058
# Terminal 2 — frontend (points at AGENT_URL=http://localhost:8058)
cd ../reglens-frontend && npm install && npm run dev:ui   # http://localhost:3000
```

Chat history persists via a stable thread id backed by the LangGraph Postgres
checkpointer — reloading replays the conversation without any cloud service.

### Session ID Format

`{user_uuid}~{random_uuid}` — the user UUID prefix enables ownership checks.

## Workflow

```
triage → discover → retrieve → detect → validate (≤3 retries) → HITL → report
   |                    ^                                        |
   |                    +──────── refine (reviewer feedback, ────+
   |                              optionally exhaustive)
   +→ casual / off-topic / unanswerable: short reply, END (no retrieval)
```

All sludge findings require human expert approval before a report is
generated. At the HITL gate the CLI shows every finding with its verbatim
citations, sources, and evidence-based confidence, and the reviewer has
three options: **approve** (publish), **reject** (discard), or **refine**
(send feedback back to the analyst for another pass — optionally
escalating to an exhaustive full-corpus sweep when the retrieval-based
findings were not satisfying). Pre-rulemaking checks and cross-border
comparisons are direct agent calls (advisory comparative analysis) and
generate audit records.

## Database Design Principles

- No FK constraints (enforced in application)
- UUIDs from `uuid.uuid4()` (never DB-generated)
- Link tables for all relationships (`document_chunk`, `finding_provision`, `session_finding`)
- Index every link table column
- Status on entity table + history in log table
- No triggers

## Deployment for African Regulators

Single Docker container + Neon serverless Postgres (pgvector built in).
Data residency options include AWS af-south-1 (Cape Town) via Neon's
region selection.

```bash
docker-compose up reglens-api

# Run ingest as a one-off
docker-compose run --rm reglens-ingest
```

## Submission Docs

- `docs/concept_note.md` — CDIR hackathon concept note
- `docs/thesis.md` — technical system description
- `docs/bon_fintech_youth_programme_note.md` — Bank of Namibia Fintech Youth Programme submission note

## License

MIT
