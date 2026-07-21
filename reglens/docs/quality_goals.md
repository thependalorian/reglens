# RegLens Quality Standards

## Why This Document Exists

RegLens findings are acted on by regulators. A wrong finding causes
a public consultation, a legal challenge, or a misdirected compliance
burden on supervised firms. These goals define what "good enough to act on"
means — and what automated checks enforce before a finding reaches a human.

---

## 1. Citation Quality

### Goal 1.1 — Zero Fabricated Citations
**Target:** 0% of findings contain citations not verbatim-verifiable in
the ingested corpus.
**Measurement:** The citation validator runs substring-match against retrieved
chunks on every finding before HITL. `CitationValidation.is_valid = True`
is a precondition for HITL approval, not a suggestion.
**Failure mode:** Finding reaches HITL with unverified citation.
**Alert threshold:** single fabricated citation per run = P0 defect.

### Goal 1.2 — Citation Completeness
**Target:** Every finding has ≥ 1 source_provision and ≥ 1
overlapping_provision, each with chunk_uid present.
**Measurement:** `finding.source_provisions` and
`finding.overlapping_provisions` are non-empty lists; every entry
contains a `chunk_uid` field.
**Acceptable exception:** A cumulative sludge finding may have source
only (no overlapping provision if the accumulation is within one instrument).
Must be noted in rationale.

### Goal 1.3 — Source Independence
**Target:** For horizontal sludge findings, source and overlapping
citations must come from different `document_uid`s.
**Measurement:** chunk_uid of source vs overlapping provision traces
to different document rows in DB.
**Failure mode:** Both citations in the same document — agent may have
found cross-references rather than genuine duplication.

---

## 2. Finding Quality

### Goal 2.1 — Severity Calibration
**Target:** ≥ 85% of HIGH severity findings cite at least one of the
calibration anchors defined in `SEVERITY_CALIBRATION` (cross-border
cost >20 days, legal uncertainty, inclusion impact, bilateral coordination
required).
**Measurement:** Human reviewer at HITL checks severity against anchors
and records agree/disagree in `review.description`.
**Tracking:** `finding_log` records reviewer severity override if applied.

### Goal 2.2 — Minimum Evidence per Finding
**Target:** 100% of horizontal findings have evidence from ≥ 2 independent
document sources. 100% of vertical findings trace ≥ 2 regulatory stack layers.
**Measurement:** Automated check in `validate_node` before routing to HITL:
count distinct `document_uid`s across a finding's citations.
**Failure mode:** Single-source finding with `confidence_score > 0.45`.
Must be caught and flagged before HITL.

### Goal 2.3 — Sludge vs Policy Ambiguity Discrimination
**Target:** < 5% of findings are false positives (flagged as sludge
but representing intentional policy design).
**Measurement:** Human reviewer at HITL records false positive in
`review.decision = "needs_revision"` with notes.
**Tracking:** Monthly: `SELECT COUNT(*) FROM review WHERE decision =
'needs_revision'` / total findings reviewed.

### Goal 2.4 — Confidence Score Honesty
**Target:** Findings with `confidence_score < 0.65` must include
"single-source evidence" or "limited corpus coverage" in rationale.
**Measurement:** Automated string check on rationale field before
routing to HITL.
**Rejection:** Finding with confidence < 0.65 and no qualifier in
rationale is sent back to detect_node for correction.

---

## 3. Retrieval Quality

### Goal 3.1 — Search Coverage
**Target:** Each analysis run makes ≥ 3 distinct `retrieve_regulatory_documents`
calls with different query angles before producing findings.
**Measurement:** Count tool calls logged in `audit_log` with
`log_type = 'retrieve'` per session.
**Failure mode:** Fewer than 3 retrieves — findings may reflect a single
semantic angle, missing orthogonal overlaps.

### Goal 3.2 — Chunk Diversity
**Target:** Retrieved chunks for a finding cover ≥ 2 of the 3 sludge
types' evidence requirements (based on chunk_uid diversity).
**Measurement:** Post-run: for each finding, trace chunk_uids back to
document_uids. Flag runs where all chunks come from ≤ 2 documents.

### Goal 3.3 — Hybrid Search Balance
**Target:** ≥ 30% of top-10 results by combined_score come from
the full-text (keyword) component rather than vector similarity alone.
**Measurement:** `text_similarity > 0` for ≥ 3 of the top-10 chunks
returned per query.
**Why:** Legal terms (article numbers, defined terms, thresholds) are
keyword matches, not semantic. Pure vector search misses them.

---

## 4. Guardrail Quality

### Goal 4.1 — HITL Approval Rate
**Target:** ≥ 90% of sessions that reach HITL are approved
(not rejected).
**What it measures:** If approval rate drops, the validator is not
catching bad findings before HITL — reviewers are doing the validator's job.
**Action on failure:** Review the last 10 rejected sessions; improve validator precision.

### Goal 4.2 — Validator Iteration Rate
**Target:** ≤ 20% of sessions require 2 or more validation iterations.
≤ 5% require 3 iterations (the maximum before fallback).
**Measurement:** `SELECT iteration_count, COUNT(*) FROM session
GROUP BY iteration_count`.
**What it measures:** High iteration rate = detector producing weak
citations consistently = prompt or retrieval quality problem.

### Goal 4.3 — Fallback Rate
**Target:** < 2% of sessions reach the fallback node
(max iterations without valid citations).
**Alert threshold:** > 5% fallback rate in any 7-day period = P1 defect.
Investigate corpus quality or prompt regression.

---

## 5. Cross-Border Analysis Quality

### Goal 5.1 — Harmonisation Score Calibration
**Target:** Scores are not clustered at 0.5 (which indicates the model
is defaulting rather than calibrating). Distribution should show
variance across the 0.0–1.0 range.
**Measurement:** Standard deviation of `harmonisation_score` across
all compare sessions > 0.10.
**Failure mode:** SD < 0.10 = model ignoring calibration anchors.

### Goal 5.2 — Gap Classification Specificity
**Target:** < 20% of gaps classified as MISSING (the least specific type).
A well-calibrated run should surface THRESHOLD_DIFFERENCE,
TERMINOLOGY, and SCOPE gaps — not just "A has it, B doesn't".
**Measurement:** `SELECT divergence_type, COUNT(*) FROM gap
GROUP BY divergence_type` — MISSING should not dominate.

### Goal 5.3 — Coordination Tier Accuracy
**Target:** 100% of coordination recommendations specify a tier
(editorial / bilateral / regional body / international standard).
**Measurement:** `recommendation` field contains one of the four
tier keywords.

---

## 6. Ingestion Quality

### Goal 6.1 — Metadata Extraction Coverage
**Target:** ≥ 85% of ingested documents have `regulatory_body` ≠
"Unknown" and `domain` ≠ "general".
**Measurement:** `SELECT COUNT(*) FROM document WHERE metadata->>'regulatory_body' = 'Unknown'`
/ total active documents.
**Action on failure:** Review extraction prompts; add document-type-specific
examples.

### Goal 6.2 — Chunk Word Count Distribution
**Target:** ≥ 95% of chunks have `token_count` between 50 and 1,000.
**Measurement:** `SELECT COUNT(*) FROM chunk WHERE token_count < 50
OR token_count > 1000` / total chunks.
**Failure modes:**
- < 50 words: fragment — no useful context for retrieval
- > 1,000 words: too long — dilutes similarity scores

### Goal 6.3 — Parser Quality by Source Type
**Target:** Docling-parsed PDFs produce chunks with `token_count > 80`
on average (raw PyMuPDF text produces < 40 on complex tables).
**Measurement:** Log parser used per document in `document.metadata.parser`;
compare average chunk token_count by parser.

---

## 7. System Quality

### Goal 7.1 — End-to-End Latency
**Target:**
- `discover + retrieve`: < 5 seconds
- `detect`: < 45 seconds
- `validate`: < 30 seconds
- Full run (no HITL wait): < 120 seconds
**Measurement:** `audit_log` timestamps per node; alert if any node
exceeds 2× target.

### Goal 7.2 — Availability
**Target:** API health endpoint returns `db_status: connected`
for ≥ 99% of uptime checks (1-minute interval).

### Goal 7.3 — Cost per Analysis
**Target:** < $2.00 USD per full sludge analysis run (corpus of
≤ 50 documents, ≤ 15 findings).
**Measurement:** Track OpenAI token usage per session via LangFuse.
Model tiering (gpt-4o for analysis, gpt-4o-mini for extraction)
is the primary lever.

---

## Quality Tracking Queries

```sql
-- Weekly quality dashboard — run every Monday
SELECT
    DATE_TRUNC('week', s.created_at)        AS week,
    COUNT(s.session_uid)                    AS total_sessions,
    AVG(a.iteration_count)                  AS avg_validation_iterations,
    SUM(CASE WHEN s.status = 'fallback_complete' THEN 1 ELSE 0 END)
                                            AS fallback_count,
    SUM(CASE WHEN r.decision = 'approved' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(r.review_uid), 0)::float
                                            AS hitl_approval_rate,
    SUM(CASE WHEN r.decision = 'needs_revision' THEN 1 ELSE 0 END)
                                            AS false_positive_count
FROM session s
LEFT JOIN audit_log a ON a.session_uid = s.session_uid
    AND a.log_type = 'validate'
LEFT JOIN review r ON r.session_uid = s.session_uid
WHERE s.created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY 1 DESC;

-- Metadata extraction coverage
SELECT
    ROUND(
        100.0 * SUM(CASE WHEN metadata->>'regulatory_body' != 'Unknown' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 1
    )                                       AS pct_body_known,
    ROUND(
        100.0 * SUM(CASE WHEN metadata->>'domain' != 'general' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 1
    )                                       AS pct_domain_known,
    COUNT(*)                                AS total_documents
FROM document
WHERE status = 'active';

-- Chunk quality distribution
SELECT
    CASE
        WHEN token_count < 50   THEN 'fragment (<50)'
        WHEN token_count <= 150 THEN 'short (50-150)'
        WHEN token_count <= 800 THEN 'good (150-800)'
        WHEN token_count <= 1000 THEN 'long (800-1000)'
        ELSE 'oversized (>1000)'
    END                                     AS bucket,
    COUNT(*)                                AS chunk_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM chunk
WHERE status = 'active'
GROUP BY 1
ORDER BY 2 DESC;
```
