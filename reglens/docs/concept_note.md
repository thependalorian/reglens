# RegLens: Adaptive Agentic Regulatory Intelligence
**CDIR Global 'Agentic Regulator' Hackathon — Concept Note**
**Submission Date: 31 July 2026**

---

## 1. Problem Space

RegLens addresses three interconnected regulatory challenges that are
acutely felt across Africa, SADC, and emerging economies globally —
but are not limited to any region.

### The Capacity Trap

Financial regulators across Africa face a structural crisis: they are
expected to supervise rapidly digitising financial systems, implement
international standards (FATF, Basel, ISO 20022), and now govern
agentic AI in payments and fraud — all with flat or shrinking resources.
The Bank of Namibia, NAMFISA, the South African Reserve Bank, the Bank of
Botswana, and their SADC peers are each independently interpreting the same
international standards, producing fragmented national implementations that
create compliance friction for cross-border firms and correspondent banking
relationships.

This is policy sludge — and it is not unique to Africa. But Africa carries
a disproportionate burden because:

1. **Resource constraints are steeper.** A central bank with a small
   supervisory team cannot spend 40 person-years consolidating circulars
   (as the Reserve Bank of India did). The same task must take hours,
   not years.

2. **Regulatory fragmentation is higher.** SADC alone has 16 member states,
   each with distinct regulatory frameworks for payments, AML/CFT, and
   financial inclusion — built independently, often with limited
   cross-border coordination infrastructure.

3. **The stakes of getting it wrong are higher.** Cross-border remittances
   are a primary income source for millions of households across SADC.
   AML/CFT de-risking already constrains correspondent banking access.
   Additional regulatory friction directly reduces financial inclusion.

4. **The opportunity is greatest.** Africa's mobile-first payment
   infrastructure, expanding fintech sector, and ongoing SADC financial
   integration create the conditions for leapfrog — if regulators can
   keep pace.

### Three Problem Spaces

**Track 2 — AI-Driven Fraud & Scams / Track 3 — Agentic Payments:**
Agentic AI in mobile payments (the dominant financial access channel
across SADC) creates fraud vectors at machine speed. Regulators need
equivalent machine-speed oversight capacity — which requires freeing
supervisory bandwidth currently consumed by sludge. The ADB (2026)
estimates regulatory divergence imposes 5-10% of annual revenue on
financial institutions, an aggregate global drag of ~$780 billion annually.

**Policy & Regulation:**
New AML/CFT circulars, payment system regulations, and fintech
frameworks are drafted without systematic checks against existing
instruments. The result: cumulative sludge that particularly burdens
smaller regulators who must implement every layer without the teams
to audit for overlap.

**Cross-regulatory & Cross-border Collaboration:**
SADC's cross-border payment integration agenda (real-time gross settlement
linkages, cross-border open banking, ISO 20022 adoption) requires
regulatory interoperability. Currently, each bilateral relationship
requires months of manual framework comparison. The National Bank of
Georgia's pilot comparing open banking frameworks across trade partners
identified 8,000+ divergences automatically — RegLens brings that
capability to any pair of frameworks in minutes.

---

## 2. Solution

RegLens is an **adaptive agentic AI system** that provides three
capabilities from a single corpus. It is fully agnostic of jurisdiction,
regulator, and domain — it works with whatever regulatory documents
are ingested.

### Use Case 1: Regulatory Sludge Detection
Detects horizontal (cross-body overlaps), vertical (stack accumulation),
and cumulative (time-layered) sludge across any regulatory corpus.

**SADC example:** Ingest AML/CFT regulations from Namibia, South Africa,
Botswana, and Zambia alongside FATF Recommendations. RegLens identifies
where each national implementation diverges from the international
standard and from each other — the exact gap analysis needed for SADC
regulatory convergence programmes.

### Use Case 2: Pre-rulemaking Policy Check
Compares a draft regulation against the existing corpus before publication.
Identifies conflicts and duplication at the point of drafting — preventing
sludge at source rather than cleaning it up afterward.

**Namibia example:** Bank of Namibia drafts a new Payment System
Determination. Before publication, RegLens checks it against existing
determinations, SADC payment system guidelines, and FATF recommendations —
flagging overlaps and contradictions in minutes.

### Use Case 3: Cross-border Gap Analysis
Compares two regulatory frameworks on the same topic. Returns a structured
gap analysis, divergence classification, harmonisation score
(0 = divergent, 1 = harmonised), and concrete coordination recommendations.

**SADC example:** Compare the Namibian AML framework vs the South African
framework on customer due diligence — producing the agenda for bilateral
regulatory coordination that previously required months of manual review
and cross-border workshop sessions.

---

## 3. Architecture

```
+------------------------------------------------------------------+
|  Regulatory Corpus (any jurisdiction, any domain)                 |
|  Statutes . Circulars . Handbooks . Standards . Drafts            |
|                                                                   |
|  African/SADC examples: BoN . NAMFISA . SARB . FSCA . ESAAMLG     |
|  International: FATF . Basel Committee . ISO 20022 . BIS          |
+---------------------------+---------------------------------------+
                            |
        Parsing: LlamaParse -> Docling (local) -> plain text
        LLM metadata extraction per document on ingest
        Discovers: regulatory_body, domain, document_type,
                   regulatory_level — from the document itself
                            |
                            v
+------------------------------------------------------------------+
|  Neon Postgres + pgvector                                         |
|  document -> document_chunk -> chunk (no FK, link tables)         |
|  Hybrid search: vector similarity + full-text keyword             |
+------------+---------------------------------+-------------------+
             |                                 |
             v                                 v
   USE CASES 1 & 2                       USE CASE 3
   LangGraph Workflow                    Direct Agent Call
   discover -> retrieve                  Cross-border Agent
   -> detect -> validate (<=3)           (retrieves from both
   -> HITL -> report                     frameworks simultaneously)
                                         Returns gap analysis +
   USE CASE 2: draft injected            harmonisation score
   as comparison target
```

**Stack**: Python 3.11 · Pydantic AI 0.3.5 · LangGraph 0.5.3 · FastAPI ·
Neon (serverless PostgreSQL + pgvector) · OpenAI API

**Five Pydantic AI Agents:**
1. `sludge_detector` — adaptive prompt from corpus_map, `SludgeAnalysis` structured output
2. `citation_validator` — citation guardrail, `CitationValidation` output (max 3 iterations)
3. `report_generator` — streaming remediation report, adaptive to corpus context
4. `precheck_agent` — draft vs existing corpus conflict detection, `SludgeAnalysis` output
5. `crossborder_agent` — gap analysis + harmonisation scoring, `CrossBorderAnalysis` output

**Adaptivity mechanism**: During ingestion, a lightweight LLM call extracts
regulatory metadata per document (body, domain, type, level). A corpus
discovery node aggregates this before each analysis run, building a
`corpus_map` that dynamically shapes all downstream prompts — no hardcoded
jurisdiction or domain assumptions anywhere in the code.

---

## 4. Mandatory Guardrails

**Human-in-the-loop:** Hard LangGraph workflow interrupt after validation.
No sludge finding is published without expert approval via
`POST /api/reglens/approve`. For regulators with small teams, the HITL
step surfaces only validated, citation-traced findings — minimising the
expert review burden while preserving regulatory accountability.
Cross-border gap analysis does not require HITL (comparative analysis,
not regulatory action) but generates an audit record.

**Auditability & Traceability:** Every finding cites exact provisions
from the ingested corpus (`source_provisions`, `overlapping_provisions`).
Every gap in the cross-border analysis cites the specific provision
present in A but absent in B. Append-only `audit_log` and `finding_log`
tables record all transitions with timestamps and user identifiers —
meeting the audit requirements of central bank governance frameworks.

**Safety:** All recommendations are explicitly advisory. The system is
positioned as decision-support for regulatory experts, not as a
decision-maker. The citation validator actively distinguishes genuine
sludge from intentional policy design space.

**Cyber Risk:** Public/synthetic regulatory corpora only — no confidential
supervisory data. The database (Neon Postgres) is server-side only —
no browser-facing access path exists; all corpus interaction goes
through the authenticated API. Local Docling parsing means no corpus
data needs to leave the regulator's environment during ingestion.

---

## 5. Transfer and Scale Potential

### Immediate applicability — SADC
16 member states. The same FATF standards, implemented 16 different ways.
RegLens can compare any pair or group of national implementations against
the international standard and each other — without manual effort.

Priority pairs for SADC cross-border work:
- Namibia and South Africa (dominant remittance corridor)
- Namibia and Botswana (SADC payment integration pilot)
- SADC members vs FATF Recommendations (compliance gap mapping)
- SADC frameworks vs ISO 20022 (real-time payment interoperability)

### Continental reach — Africa
ECOWAS, COMESA, EAC — each regional economic community has its own
financial integration agenda with the same cross-border regulatory
fragmentation problem. RegLens deploys identically across all of them.
ESAAMLG (Eastern and Southern Africa Anti-Money Laundering Group)
framework comparisons are a direct use case.

### Global
The system is fully adaptive. Ingest EU MiFIR + CFTC derivatives rules:
it detects the field-definition divergence. Ingest Basel III
implementations across G20 members: it maps where each jurisdiction
diverged from the international standard. The ADB's Pacific programme
demonstrates the same leapfrog pattern for resource-constrained
regulators there. The architecture does not change — only the corpus.

**Deployment**: single Docker container + Neon serverless Postgres,
with African data residency options (AWS af-south-1 Cape Town via
Neon region selection). Ingest new regulatory documents and re-run
analysis — the system adapts automatically.

---

## 6. Impact Metrics

Based on validated precedents:
- **Stanford HAI**: >36% of mandated reporting requirements identified
  for deletion or consolidation in pilot review
- **FCA MiFIR analysis**: 65 fields reduced to 52 = £100M/year estimated saving
- **RBI**: 9,000 circulars consolidated to 244 master directions;
  >40 person-years of manual effort — RegLens compresses this to hours
- **National Bank of Georgia**: months of manual cross-border framework
  comparison automated; 8,000+ divergence items identified
- **SADC potential**: 16 member states = 120 bilateral AML framework
  pairs — each currently requiring months of manual comparison

For a central bank with limited supervisory headcount, converting months
of framework comparison to minutes is not incremental — it is
transformational.

---

## 7. Team

Wiebe Geldenhuys — System Architecture, Database Design
Jerobeam Nambili — Product Requirements, SADC Field Context
George Nekwaya — Development, Analytics

**Regional context:** This team operates in the Namibian fintech and
payment infrastructure sector. The problem RegLens solves is one we
encounter operationally: regulatory fragmentation across SADC
jurisdictions creates real friction for cross-border payment operations.
RegLens is built from this lived context — and designed to work anywhere.
