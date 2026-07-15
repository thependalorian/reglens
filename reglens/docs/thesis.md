# RegLens: Adaptive Agentic Regulatory Sludge Detection
## Technical System Description

---

### Abstract

RegLens is a production agentic AI system for regulatory sludge detection,
pre-rulemaking policy checking, and cross-border regulatory gap analysis.
It ingests any regulatory corpus, discovers the regulatory context from the
documents themselves, and produces citation-validated remediation roadmaps
through a mandatory human-in-the-loop workflow. The system operationalises
the ADB/Cambridge "detect → validate → decide → amend → track" framework
as a LangGraph multi-agent pipeline, with Pydantic AI structured outputs
providing traceable, auditable finding records.

The core design principle is adaptivity: no jurisdiction, domain, or
regulatory body is hardcoded. The system learns what it has from the
documents ingested, enabling deployment against any regulatory corpus
without reconfiguration. It is designed from the lived reality of African
and SADC regulatory environments — where resources are constrained,
fragmentation is high, and the leapfrog opportunity is greatest — while
remaining fully adaptive to any jurisdiction or domain globally.

---

### 1. The Problem

Policy sludge is not a metaphor — it is a measurable drain on regulatory
capacity. The ADB (2026) documents three accumulation vectors:

**Horizontal**: The same obligation expressed differently across parallel
bodies. ESMA and CFTC both require derivatives trade reporting; their
field definitions diverge on ~30% of data points, forcing global firms to
maintain duplicate reporting pipelines. Helen Packard (FCA) identified
this concretely: 65 data fields required under MiFIR transaction reporting;
analysis showed 52 were sufficient — a potential £100m annual saving.

**Vertical**: Each translation down the regulatory stack (international
standard → statute → regulation → guidance → supervisory handbook →
firm policy) adds without removing. Third-party risk management is a
documented example: straightforward expectation at the statute level,
hundreds of questionnaire items at the firm level.

**Cumulative**: New requirements layer on existing ones over time.
Board governance duties: every rule cycle adds "the board shall..."
without retiring prior obligations. The Reserve Bank of India spent
>40 person-years consolidating 9,000 circulars into 244 master directions
— a task RegLens accelerates to hours.

The Stanford HAI/RegLab (2025) pilot demonstrates AI-assisted review
can identify deletion or consolidation opportunities in >36% of mandated
reporting requirements.

RegLens implements this at production scale.

#### 1.1 The Problem in African Context

Policy sludge is a global problem. Its consequences fall hardest on
regulators with the least capacity to absorb them.

**SADC regulatory fragmentation:** The Southern African Development
Community's 16 member states each maintain independent regulatory
frameworks for payments, AML/CFT, financial inclusion, and consumer
protection. All are implementing the same international standards
(FATF Recommendations, Basel III, ISO 20022) but doing so independently.
The result:

- Firms operating across Namibia, South Africa, and Botswana must
  maintain three separate AML compliance programmes for obligations
  that are substantially identical at the international standard level.
- SADC cross-border payment integration (the SADC RTGS linkage,
  cross-border open banking pilots) is slowed by regulatory
  interoperability gaps that take months of bilateral negotiation
  to identify — and longer to resolve.
- Central banks with small supervisory teams are expected to implement
  every FATF mutual evaluation recommendation, every Basel update, and
  every new fintech framework — without the capacity to audit for
  overlap with existing instruments.

**The Namibia context:** The Bank of Namibia operates in a payments
ecosystem where mobile money serves as primary financial infrastructure
for a large portion of the population. Regulatory frameworks for these
systems must be interoperable with South African SARB oversight (for
rand-denominated flows), SADC payment system guidelines, and FATF
requirements — three parallel stacks, each evolving independently.

**Continental scale:** ECOWAS, COMESA, and the EAC all face equivalent
fragmentation. ESAAMLG — the Eastern and Southern Africa Anti-Money
Laundering Group — coordinates AML/CFT across its member states but
relies on manual bilateral comparison for framework alignment work.

RegLens makes this systematic, fast, and auditable — without a single
line of region-specific code. The African context is the design driver;
the implementation is entirely corpus-driven.

---

### 2. System Architecture

#### 2.1 Stack Selection

| Layer | Choice | Rationale |
|---|---|---|
| Agent framework | Pydantic AI 0.3.5 | Structured outputs (SludgeAnalysis, CitationValidation), typed tool contracts |
| Orchestrator | LangGraph 0.5.3 | Guardrail loop, HITL interrupt, checkpoint persistence |
| API | FastAPI + SSE | Streaming node progress to UI/CLI |
| Vector store | Neon Postgres + pgvector | Hybrid search (vector + full-text), serverless managed Postgres |
| Database design | No FK, app UUIDs, link tables | Portability across any Postgres-compatible DB |

#### 2.2 Database Design

The schema follows design principles established in the Ketchup DEV session
(Wiebe Geldenhuys, 7 July 2026):

1. **No foreign key constraints** — relationships enforced in application code.
   This preserves compatibility across database engines and avoids trigger
   complexity.
2. **UUIDs generated by application** — `uuid.uuid4()` in Python, not
   `DEFAULT uuid_generate_v4()`. The database never generates identifiers.
3. **Link tables for all relationships** — `document_chunk`, `finding_provision`,
   `session_finding`. Each is a plain table with two UUID columns.
4. **Index every link table column** — both columns of every link table carry
   an index. The query planner reduces from full-table scans to targeted
   lookups. (Demonstrated in session: explain output showed 3→2 row lookups
   after index addition.)
5. **Status on entity table + log table** — entity table holds current status
   for fast queries; log table holds full change history. Two operations,
   both in application layer.
6. **Generic `description` field** — all entity tables use `description`.
   SELECT queries alias it to contextually meaningful names (`document_title`,
   `citation`, `title`). This avoids verbose field names while preserving
   query clarity.
7. **No database triggers** — all state transitions happen in `db_utils.py`.
   The database is a dumb store; logic lives in the application.

#### 2.3 Adaptivity Mechanism

The system's adaptivity comes from two components:

**Ingestion extractor** (`ingestion/extractor.py`): A lightweight LLM call
(gpt-4o-mini, 200 token budget, first 3,000 chars) extracts per-document
metadata: regulatory body, domain, document type, regulatory level,
obligations present. This runs once per document at ingest time and is
stored in `document.metadata` JSONB.

**Corpus discovery node** (`workflows/nodes/discover.py`): Before any
analysis, a pure DB aggregation query reads all active document metadata
and builds a `corpus_map` — a structured summary of what is actually in
the corpus. No LLM call. No hardcoded assumptions. The corpus_map is
injected into all downstream agent prompts via `RunContext[AgentDeps]`.

This means RegLens automatically adapts to:
- A corpus of UK FCA rules → bodies=["FCA"], domains=["conduct", "markets"]
- A corpus of FATF + national AML laws → bodies=["FATF","FinCEN","FCA"],
  domains=["AML/CFT"]
- A mixed international corpus → bodies=[20+ bodies], domains=[mixed]

The detection agent's system prompt is built at runtime from the corpus_map.
The report generator adapts its structure to whatever was found.

#### 2.4 Document Parsing Hierarchy

Regulatory documents from central banks and standards bodies are almost
entirely PDFs — often scanned, multi-column, with nested tables (FATF
mutual evaluation matrices, Basel capital calculation tables). Ingestion
parses through a quality hierarchy (`ingestion/parser.py`):

1. **LlamaParse** (cloud, VLM-based) — used when `LLAMA_CLOUD_API_KEY`
   is set. Best quality for scanned PDFs and complex layouts.
2. **Docling** (local AI/ML layout model, DocLayNet) — the default.
   Preserves table structure and multi-column layouts, outputs
   structured markdown, and runs fully locally — no corpus data leaves
   the regulator's environment. This is a meaningful compliance property
   for central bank deployments without external network access.
3. **Plain text** — `.txt`/`.md` read directly.

Both parsers output markdown, so the downstream chunker processes all
sources identically.

---

### 3. Workflow Design

#### 3.1 Graph Structure

START → triage ──casual/off-topic──► END (short reply, no retrieval)
│
analysis
│
discover → retrieve → detect → validate
↑ │
└─invalid──┘ (max 3 iterations)
│
valid
│
hitl ──rejected──► END
│
approved
│
report → END

The triage node (mini model, structured `TriageDecision` output) is the
Anthropic routing pattern: it classifies every request before any
retrieval happens, so greetings, small talk, and out-of-scope requests
cost one mini-model call instead of a full analysis run. It fails open —
a triage error routes to analysis, never silently drops a real request.


#### 3.2 Node Responsibilities

| Node | Agent | Purpose |
|---|---|---|
| discover | None (DB query) | Build corpus_map from document metadata |
| retrieve | None (hybrid search) | Fetch relevant chunks for query |
| detect | sludge_detector (gpt-4o) | Identify and classify sludge findings |
| validate | citation_validator (gpt-4o) | Verify all citations against corpus |
| hitl | None (state update) | Pause for human expert review |
| report | report_generator (gpt-4o) | Generate remediation roadmap |

#### 3.3 Guardrail Loop

The validate node returns a `CitationValidation` object. If `is_valid=False`
and `iteration_count < 3`, the workflow routes back to detect with the
validator's feedback injected into the detection query. The detector corrects
its citations on the next pass. After 3 iterations, the workflow proceeds
to HITL regardless — a fallback prevents infinite loops.

This implements the ADB's quality control recommendation: "Properly trained
AI tools must be supported by evaluation benchmarks and human expert
validation. Their outputs must be traceable to source text."

#### 3.4 HITL Implementation

The HITL node sets `approval_status = "pending"` and the workflow pauses
at a LangGraph checkpoint (MemorySaver in dev, PostgresSaver in production).
The findings surface to a reviewer via `GET /api/reglens/findings/{session_id}`.

The reviewer sees every finding rendered with its verbatim citations,
source documents, and evidence-based confidence (CLI `review` output),
then calls `POST /api/reglens/approve` with one of three actions:

- **approve** — publish the findings; workflow resumes into report
  generation.
- **reject** — end the workflow; nothing is published.
- **refine** — the reviewer's notes are injected as expert feedback and
  the workflow routes back to retrieval and detection for another pass;
  `exhaustive: true` escalates the re-run to a full-corpus sweep. The
  refined findings return to the HITL gate — the human steers each
  cycle, so the loop cannot run away.

Each decision calls `workflow.update_state()` followed by
`workflow.astream(None, config)` to resume from the checkpoint.

This is a hard workflow interrupt — not a soft UI prompt. The Postgres
checkpointer preserves state across process restarts, so a pending
review survives an API redeploy.

---

### 4. Agent Design

#### 4.1 Three-Agent Architecture

**sludge_detector**: The primary analytical agent. System prompt is built
dynamically from `corpus_map` at `RunContext` creation time. Has two tools:
`retrieve_regulatory_documents` (broad hybrid search returning formatted
chunks) and `search_for_specific_provision` (targeted lookup to verify a
citation before it enters a finding). Outputs structured `SludgeAnalysis`
(Pydantic `output_type`).

**citation_validator**: Guardrail agent. System prompt is static (the
validation criteria don't change with corpus context). Has one tool:
`verify_provision_in_corpus` — targeted hybrid search for a specific
citation. Outputs structured `CitationValidation`.

**report_generator**: Synthesis agent. System prompt built from corpus_map
for adaptive report structure. No tools — works from state passed in
the user query. Streams output for UX responsiveness.

#### 4.2 Model Tiering

| Agent | Model | Rationale |
|---|---|---|
| sludge_detector | gpt-4o | Primary analytical task — needs reasoning depth |
| citation_validator | gpt-4o | Legal accuracy is high-stakes |
| report_generator | gpt-4o | Complex synthesis |
| precheck_agent | gpt-4o | Draft-vs-corpus conflict analysis |
| crossborder_agent | gpt-4o | Gap analysis + harmonisation scoring |
| metadata extractor | gpt-4o-mini | Cost control — 200 tokens, simple extraction |
| corpus discovery | None | Pure DB aggregation — no LLM cost |

#### 4.3 Additional Use-Case Agents

Two further agents extend RegLens beyond sludge detection without
modifying the main workflow — both are direct agent calls exposed as
streaming endpoints:

**precheck_agent** (`workflows/nodes/precheck.py`): Pre-rulemaking
check. Takes a draft regulatory text and compares it against the
existing corpus via the `search_existing_corpus` tool. Reuses the
`SludgeAnalysis` output type — each finding is a conflict, duplication,
or vertical-accumulation risk the draft would introduce. Exposed at
`POST /api/reglens/precheck`.

**crossborder_agent** (`workflows/nodes/crossborder.py`): Cross-border
gap analysis. Takes two framework labels, two metadata filters, and a
topic. Two retrieval tools (`retrieve_framework_a_provisions`,
`retrieve_framework_b_provisions`) apply client-side metadata filters
over hybrid search so the agent can query each framework independently.
Outputs a structured `CrossBorderAnalysis`: per-gap divergence
classification (missing / threshold_difference / terminology /
procedural / scope), a harmonisation score (0.0–1.0), key friction
points, and coordination recommendations. Exposed at
`POST /api/reglens/compare`.

#### 4.4 Factuality Architecture

RegLens treats "is the agent telling the truth" as an engineering
problem with four mechanical layers, following the "ground truth from
the environment" principle (Anthropic, Building Effective Agents):

1. **Grounded citations.** Findings cite through a structured `Citation`
   model: document title, provision reference, a verbatim quote (max
   400 chars), and the `chunk_uid` of the retrieved chunk it came from.
   Retrieved chunks expose their `chunk_uid` in the `[SOURCE ...]`
   header so the model copies, never invents, the pin. Provision rows
   in the database store the resolved `document_uid` — every citation
   is traceable from report to source document.

2. **Mechanical verification before LLM validation.**
   `verify_citations_mechanically()` normalizes whitespace/case and
   substring-matches every verbatim quote against the retrieved corpus
   text. This runs deterministically (no LLM, no cost) inside
   `detect_node` and again in `validate_node`; the adversarial
   citation_validator agent then adjudicates only the quotes the
   mechanical check could not verify.

3. **Evidence-based confidence.** The model's self-reported
   `confidence_score` is overridden with
   `min(verified_citations / total_citations, self_score)`.
   A finding with no citations scores 0.0. The model cannot award
   itself credibility it has not earned in quotes.

4. **Coverage disclosure.** Retrieved chunks accumulate across all tool
   calls (deduped by `chunk_uid`); the detection prompt requires at
   least three retrieval angles before conclusions. The report's
   mandatory first section states exactly which documents were examined
   out of the corpus total. For complete sweeps, exhaustive mode
   (`analyze --exhaustive`) map-reduces the entire corpus: a mini-model
   obligation digest per document, then cross-document synthesis by the
   detector — roughly one extra LLM call per corpus document.

**Personas.** Each agent's system prompt opens with a professional
identity, background, goal, and standard of evidence (the detector
"never asserts what it cannot quote"; the validator's goal is "zero
fabricated citations reach a regulator"), and closes with a shared
FACTUAL DISCIPLINE block: quote-or-omit, say "not found in the ingested
corpus" rather than guess, distinguish evidence from inference, never
claim corpus-wide completeness. All factual agents run at temperature 0.

---

### 5. Evaluation Framework

RegLens implements the three-dimensional evaluation Robert Wardrop
(REGG Genome, Cambridge) proposed in the CDIR forum:

**Speed**: Document corpus that previously required weeks of manual review
(as documented in the RBI case: 40+ people over a year for 9,000 circulars)
is processed in hours by the ingestion + detection pipeline.

**Coverage**: The hybrid search (vector + full-text) covers the entire
ingested corpus exhaustively, surfacing both expected sludge and unexpected
cross-domain overlaps that manual reviews miss.

**Quality**: The citation guardrail loop, human validation checkpoint,
and full audit trail (provision-level traceability, status change logs)
implement the "confidence infrastructure" Wardrop identified as essential
for supervisory-grade AI use: reliable consistent anchors, deterministic
source tracing, human responsibility for final validation.

---

### 5a. African Regulatory Bodies — Corpus Examples

RegLens ingests any regulatory document. For SADC/African deployments:

**National regulators (examples):**
- Bank of Namibia (BoN) — payment system determinations, FIA regulations
- NAMFISA — non-bank financial institutions supervision
- South African Reserve Bank (SARB) — prudential standards, NPS regulations
- Financial Sector Conduct Authority (FSCA) — conduct framework
- Bank of Botswana (BoB), Bank of Zambia (BoZ), Bank of Tanzania (BoT),
  Reserve Bank of Zimbabwe (RBZ), Central Bank of Kenya (CBK)

**Regional bodies:**
- SADC Committee of Central Bank Governors (CCBG)
- ESAAMLG — AML/CFT standards and mutual evaluation reports
- COMESA Monetary Institute
- African Development Bank (AfDB) regulatory guidance

**International standards applied in African context:**
- FATF Recommendations + Mutual Evaluation Reports for member states
- Basel III/IV implementation guidelines
- ISO 20022 for African RTGS linkage projects
- BIS Innovation Hub outputs relevant to African payment systems

All of these are ingested identically — the system adapts to whatever
is provided. The `regulatory_body` and `domain` fields are extracted
by LLM from document content, not configured manually.

---

### 5b. SADC Cross-Border Use Cases in Detail

#### AML/CFT Framework Harmonisation

**Scenario:** SADC is pursuing regulatory convergence on AML/CFT to
reduce correspondent banking friction. Current process: bilateral
workshops between central banks, manual document comparison, months
of negotiation.

**RegLens approach:**
1. Ingest FATF Recommendations + national AML/CFT frameworks for
   SADC member states with documents available
2. Run `compare` with `filter_a={"regulatory_body": "FATF"}` and
   `filter_b={"regulatory_body": "BoN"}` on topic "customer due diligence"
3. RegLens returns: gap analysis, divergence classification,
   harmonisation score, and concrete convergence recommendations
4. Repeat for each bilateral pair — or run `analyze` across the full
   multi-jurisdiction corpus for a horizontal sludge map

This is the National Bank of Georgia pilot (8,000+ divergences
identified) applied to SADC at regional scale.

#### Payment System Regulation — Namibia Pre-rulemaking

**Scenario:** Bank of Namibia is drafting a new determination on
e-money interoperability to support SADC cross-border mobile money flows.

**RegLens approach:**
1. Corpus already contains: existing BoN payment determinations,
   SADC payment system guidelines, FATF guidance on mobile money,
   NPS Act provisions
2. Run `precheck` with the draft determination text
3. RegLens identifies: conflicts with existing determinations,
   obligations already covered by the NPS Act, divergences from
   SADC guidelines
4. The BoN team reviews the findings before drafting the final instrument

Result: the draft arrives at public consultation cleaner, with fewer
unintended overlaps and better SADC alignment.

#### ESAAMLG Mutual Evaluation Preparation

**Scenario:** A SADC member state is preparing for FATF/ESAAMLG mutual
evaluation. The review team needs to identify gaps between the national
AML/CFT framework and the FATF Recommendations.

**RegLens approach:**
1. Ingest national AML/CFT laws, regulations, and guidelines +
   the FATF 40 Recommendations
2. Run `analyze "Find gaps between national AML/CFT framework and FATF
   recommendations"`
3. Corpus discovery identifies national framework vs international standard
4. Detection identifies missing obligations (vertical gaps) and
   obligations present but inconsistently defined (horizontal sludge)
5. The report provides a prioritised gap remediation roadmap for
   the evaluation

---

### 6. Deployment

#### Minimal deployment (demo):
```bash
# 1. Run schema
# Apply schema to Neon: psql "$DATABASE_URL" -f sql/schema.sql

# 2. Ingest regulatory documents
python -m ingestion.ingest --path ./data --recursive

# 3. Start API
uvicorn agent.api:app --host 0.0.0.0 --port 8058

# 4. Run analysis
python cli.py --port 8058

Production deployment:
Docker Compose with two services (API + background ingest worker),
Neon serverless Postgres for pgvector + application tables,
PostgresSaver for LangGraph HITL checkpoints (same DATABASE_URL).

```

#### Deployment for African Regulators

**SADC multi-regulator deployment:** Multiple central banks contribute
documents to a shared corpus. Each bank's documents are tagged with
`regulatory_body` automatically during ingestion. Cross-border comparison
runs across the shared corpus with jurisdiction filters — no
infrastructure changes.

**Cost profile:**
- Neon's free tier handles a substantial regulatory document corpus
- LLM API cost per analysis is dominated by the detection/validation
  loop; metadata extraction is capped at 200 tokens per document
- No per-seat licensing, no region restrictions
- Data residency options: AWS af-south-1 (Cape Town), GCP africa-south1
- Docling parsing runs fully locally — no corpus data leaves the
  regulator's environment during ingestion

#### Web interface (CopilotKit + AG-UI)

The same LangGraph workflow that backs the CLI also drives a web workspace
(`reglens-frontend/`, Next.js + CopilotKit v2). The backend mounts the graph
as an AG-UI protocol endpoint (`/agui`, via `ag-ui-langgraph`); the frontend's
CopilotKit runtime brokers to it with `LangGraphHttpAgent`. The deployment is
self-hosted end to end — no managed Intelligence service, so no corpus or
conversation data leaves local infrastructure, and chat history persists
through the LangGraph Postgres checkpointer keyed by a stable thread id.

The UI is a single agent-driven workspace: a chat beside a shared-state canvas
that the agent updates live (the workflow stepper, coverage meter, findings,
and report all read `SludgeWorkflowState` streamed over AG-UI). Human review is
the same dynamic `interrupt()` used by the CLI, surfaced in the browser through
CopilotKit's `useInterrupt` — the reviewer approves, rejects, or refines
(optionally escalating to exhaustive) and the graph resumes with `Command`.
A Documents tab manages the ingest pipeline directly: uploads are parsed and
embedded in a background task (shown `processing → active`), and removal deletes
a document with its chunks. Regulators manage the corpus they analyze without
touching the CLI.

### 7. Limitations and Future Work

Current limitations:

Scanned/complex PDFs parse best with LlamaParse (cloud) or Docling
(local); very low-quality scans may still need manual OCR review
HITL is API-driven; a web UI for the review interface is not yet built
The citation validator cannot verify references to documents not in corpus
Future work:

Real-time sludge monitoring as new regulations are drafted
(the "sludge co-pilot" Michael Hsu described)
Machine-readable output generation (JSON-LD, XBRL) per the
ADB's computational regulation recommendations
Cross-instance corpus federation for multi-regulator analysis
Integration with regulatory drafting environments for pre-rulemaking
sludge detection
8. References
Cambridge Centre for Alternative Finance (2026). The 2026 Global AI in
Financial Services Report: Adoption, impact and risks. Cambridge: CJBS.

Hsu, M.J., Schou Zibell, L., Synsatayakul, W., Wardrop, R. (2026).
Simplifying Compliance: Cleaning Up Policy Sludge with Trained AI Tools.
ADB Briefs No. 394. Asian Development Bank.

Stanford HAI & RegLab (2025). Cleaning Up Policy Sludge: An AI Statutory
Research System. Stanford University.

Sunstein, C. (2020). Sludge: What Stops Us from Getting Things Done and
What to Do About It. MIT Press.

International Federation of Accountants & Business at OECD (2018).
Regulatory Divergence: Costs, Risks, Impacts.

African Development Bank (2024). Financial Sector Development Policy
and Strategy. AfDB Group.

Financial Action Task Force / ESAAMLG. Mutual Evaluation Reports for
SADC member states. Paris: FATF/OECD.

SADC Committee of Central Bank Governors. SADC Payment System
Oversight frameworks and integration documentation. SADC Secretariat.

ESAAMLG. Eastern and Southern Africa AML/CFT standards implementation
assessments. Dar es Salaam: ESAAMLG Secretariat.


