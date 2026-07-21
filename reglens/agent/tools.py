"""
RAG tools — adaptive search across any ingested corpus.
No hardcoded jurisdictions or domains.
Joins use link tables per Ketchup DEV design (no FK constraints).
'description' aliased as document_title in SELECT.

Search lives here as parameterized SQL against Neon Postgres —
no stored procedures, no triggers (workspace rule).
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import List
import asyncpg
from openai import AsyncOpenAI

# Best-effort provision locator patterns, applied to chunk text when the
# chunk carries no structured section metadata (documents ingested before
# section/page capture). Matches "9.1.1", "Section 4.2", "Article 9(1)",
# "Reg 12", "Part III". Deterministic — the model still quotes verbatim.
_SECTION_PATTERNS = [
    re.compile(r"\b(?:Section|Sec\.?|Article|Art\.?|Regulation|Reg\.?|Clause|Paragraph|Para\.?|Rule|Part)\s+[0-9IVXLC]+(?:[.\(][0-9a-z]+\)?)*", re.IGNORECASE),
    re.compile(r"(?m)^\s*#{1,6}\s*([0-9]+(?:\.[0-9]+)*\s+.+?)\s*$"),
    re.compile(r"\b[0-9]+\.[0-9]+(?:\.[0-9]+)*\b"),
]


def _chunk_locator(chunk: dict) -> str:
    """
    Return a copy-able provision locator for a retrieved chunk.
    Prefers structured metadata captured at ingestion (section/page); falls
    back to a best-effort match on the chunk text, and always includes the
    deterministic chunk position so a reviewer can find the exact passage.
    """
    meta = chunk.get("metadata") or {}
    section = meta.get("section") or meta.get("heading") or ""
    page = meta.get("page") or meta.get("page_number") or ""
    idx = chunk.get("chunk_index")

    if not section:
        content = str(chunk.get("content", ""))[:400]
        for pat in _SECTION_PATTERNS:
            m = pat.search(content)
            if m:
                section = (m.group(1) if m.groups() else m.group(0)).strip()
                break

    parts = []
    if section:
        parts.append(f"section={section}")
    if page not in ("", None):
        parts.append(f"page={page}")
    if idx is not None:
        parts.append(f"chunk#{idx}")
    return " | ".join(parts)


@dataclass
class AgentDeps:
    pool:             asyncpg.Pool
    embedding_client: AsyncOpenAI
    corpus_map:       dict = field(default_factory=dict)
    retrieved_chunks: List[dict] = field(default_factory=list)
    # Cumulative character budget for retrieval results returned to the model
    # across ALL tool calls in one detector run. Every call's formatted chunks
    # stay in the message history, so a multi-jurisdiction comparison that makes
    # many calls will otherwise overflow the 128k context. ~120k chars is
    # ~30k tokens — ample evidence, safely under the window with room for the
    # prompt and the model's own output.
    retrieval_char_budget: int = 120_000


async def embed_text(client: AsyncOpenAI, text: str) -> List[float]:
    resp = await client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        input=text,
    )
    return resp.data[0].embedding


def _to_vector_literal(embedding: List[float]) -> str:
    """pgvector text literal — cast with ::vector in SQL (no codec needed)."""
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


async def discover_corpus_map(pool: asyncpg.Pool) -> dict:
    """
    Aggregate document metadata from DB to build corpus context.
    Pure DB aggregation — no LLM call, no hardcoded assumptions.
    Called by discover_node before any analysis.
    """
    rows = await pool.fetch(
        """
        SELECT document_uid, description, metadata, status
        FROM document
        WHERE status = 'active'
        """
    )

    regulatory_bodies: set = set()
    domains:           set = set()
    doc_types:         set = set()
    reg_levels:        set = set()

    for row in rows:
        meta = row["metadata"] or {}
        if b := meta.get("regulatory_body"):
            if b.lower() not in ("unknown", ""):
                regulatory_bodies.add(b)
        if d := meta.get("domain"):
            if d.lower() not in ("unknown", "general", ""):
                domains.add(d)
        if t := meta.get("document_type"):
            if t.lower() != "unknown":
                doc_types.add(t)
        if l := meta.get("regulatory_level"):
            if l.lower() != "unknown":
                reg_levels.add(l)

    n_docs    = len(rows)
    n_bodies  = len(regulatory_bodies) or 1
    n_domains = len(domains) or 1

    chunk_count = await pool.fetchval(
        "SELECT count(*) FROM chunk WHERE status = 'active'"
    ) or 0

    return {
        "document_count":    n_docs,
        "corpus_chunk_count": int(chunk_count),
        "document_titles":   sorted(r["description"] or "" for r in rows),
        "regulatory_bodies": sorted(regulatory_bodies) or ["Unknown"],
        "domains":           sorted(domains) or ["General regulatory"],
        "document_types":    sorted(doc_types),
        "regulatory_levels": sorted(reg_levels),
        "coverage_summary": (
            f"{n_docs} documents from {n_bodies} regulatory "
            f"{'body' if n_bodies == 1 else 'bodies'} covering "
            f"{n_domains} {'domain' if n_domains == 1 else 'domains'}"
        ),
    }


_HYBRID_SEARCH_SQL = """
WITH vector_results AS (
    SELECT
        c.chunk_uid,
        dc.document_uid,
        c.content,
        c.chunk_index,
        1 - (c.embedding <=> $1::vector)        AS vector_sim,
        c.metadata,
        d.description                           AS doc_title,
        d.source                                AS doc_source,
        d.metadata                              AS doc_meta
    FROM chunk c
    JOIN document_chunk dc  ON c.chunk_uid    = dc.chunk_uid
    JOIN document d         ON dc.document_uid = d.document_uid
    WHERE c.embedding IS NOT NULL
      AND c.status = 'active'
      AND d.status = 'active'
),
text_results AS (
    SELECT
        c.chunk_uid,
        dc.document_uid,
        c.content,
        c.chunk_index,
        ts_rank_cd(
            to_tsvector('english', c.content),
            plainto_tsquery('english', $2)
        )                                       AS text_sim,
        c.metadata,
        d.description                           AS doc_title,
        d.source                                AS doc_source,
        d.metadata                              AS doc_meta
    FROM chunk c
    JOIN document_chunk dc  ON c.chunk_uid    = dc.chunk_uid
    JOIN document d         ON dc.document_uid = d.document_uid
    WHERE to_tsvector('english', c.content)
          @@ plainto_tsquery('english', $2)
      AND c.status = 'active'
      AND d.status = 'active'
)
SELECT
    COALESCE(v.chunk_uid,    t.chunk_uid)       AS chunk_uid,
    COALESCE(v.document_uid, t.document_uid)    AS document_uid,
    COALESCE(v.content,      t.content)         AS content,
    COALESCE(v.chunk_index,  t.chunk_index)     AS chunk_index,
    (COALESCE(v.vector_sim, 0) * (1 - $4) +
     COALESCE(t.text_sim,   0) * $4)            AS combined_score,
    COALESCE(v.vector_sim, 0)                   AS vector_similarity,
    COALESCE(t.text_sim,   0)                   AS text_similarity,
    COALESCE(v.metadata,     t.metadata)        AS metadata,
    COALESCE(v.doc_title,    t.doc_title)       AS document_title,
    COALESCE(v.doc_source,   t.doc_source)      AS document_source,
    COALESCE(v.doc_meta,     t.doc_meta)        AS document_metadata
FROM vector_results v
FULL OUTER JOIN text_results t ON v.chunk_uid = t.chunk_uid
ORDER BY 4 DESC
LIMIT $3
"""

_VECTOR_SEARCH_SQL = """
SELECT
    c.chunk_uid,
    dc.document_uid,
    c.content,
    c.chunk_index,
    1 - (c.embedding <=> $1::vector)            AS similarity,
    c.metadata,
    d.description                               AS document_title,
    d.source                                    AS document_source,
    d.metadata                                  AS document_metadata
FROM chunk c
JOIN document_chunk dc  ON c.chunk_uid   = dc.chunk_uid
JOIN document d         ON dc.document_uid = d.document_uid
WHERE c.embedding IS NOT NULL
  AND c.status = 'active'
  AND d.status = 'active'
ORDER BY c.embedding <=> $1::vector
LIMIT $2
"""


async def fetch_all_chunks(pool: asyncpg.Pool) -> List[dict]:
    """
    Exhaustive mode: return every active chunk with its document context,
    ordered by document and chunk position. No embedding search — this is
    the full corpus, used for map-reduce sweeps.
    """
    rows = await pool.fetch(
        """
        SELECT
            c.chunk_uid,
            dc.document_uid,
            c.content,
            c.chunk_index,
            c.metadata,
            d.description AS document_title,
            d.source      AS document_source,
            d.metadata    AS document_metadata
        FROM chunk c
        JOIN document_chunk dc ON c.chunk_uid    = dc.chunk_uid
        JOIN document d        ON dc.document_uid = d.document_uid
        WHERE c.status = 'active' AND d.status = 'active'
        ORDER BY d.description, c.chunk_index
        """
    )
    return [dict(r) for r in rows]


async def hybrid_search(
    pool:             asyncpg.Pool,
    embedding_client: AsyncOpenAI,
    query:            str,
    match_count:      int = 12,
) -> List[dict]:
    """
    Hybrid search (vector + full-text) across entire corpus.
    No jurisdiction filter — adaptive to whatever is ingested.
    Falls back to vector-only on error.
    """
    embedding = await embed_text(embedding_client, query)
    vector    = _to_vector_literal(embedding)

    try:
        rows = await pool.fetch(
            _HYBRID_SEARCH_SQL, vector, query, match_count, 0.3
        )
        return [dict(r) for r in rows]
    except Exception:
        rows = await pool.fetch(_VECTOR_SEARCH_SQL, vector, match_count)
        return [dict(r) for r in rows]


# Cap per-chunk content shown to the model. The detector makes several
# retrieve calls and every result stays in its message history, so unbounded
# chunk text compounds and overflows the model context
# (400 context_length_exceeded). The shown text is a prefix of the full chunk,
# so verbatim quotes from it still verify against the full content in
# deps.retrieved_chunks. Sized to keep most of a provision visible (detection
# quality) while ~12 chunks x a dozen calls stays well under 128k tokens.
_MAX_CHUNK_CHARS = 2800


def format_chunks_for_agent(chunks: List[dict]) -> str:
    """
    Format retrieved chunks for LLM context.
    document_title is aliased from document.description in SQL.
    Includes document_metadata for adaptive context.
    """
    if not chunks:
        return "No relevant regulatory documents found in corpus."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        title  = chunk.get("document_title", "Unknown")
        score  = chunk.get("combined_score") or chunk.get("similarity", 0.0)
        meta   = chunk.get("document_metadata") or {}
        body   = meta.get("regulatory_body", "")
        domain = meta.get("domain", "")
        c_uid  = chunk.get("chunk_uid", "")

        locator = _chunk_locator(chunk)

        header = f"[SOURCE {i} | {title}"
        if body:
            header += f" | {body}"
        if domain:
            header += f" | {domain}"
        if locator:
            header += f" | {locator}"
        header += f" | score={score:.3f} | chunk_uid={c_uid}]"

        content = str(chunk.get("content", ""))
        if len(content) > _MAX_CHUNK_CHARS:
            cut = content.rfind(" ", 0, _MAX_CHUNK_CHARS)
            content = content[: cut if cut > 0 else _MAX_CHUNK_CHARS] + " …[truncated — do not quote past here]"

        parts.append(f"{header}\n{content}")

    return "\n\n---\n\n".join(parts)


# ============================================================
# MECHANICAL CITATION VERIFICATION
# Ground truth from the environment: verbatim quotes are checked
# against retrieved chunk text BEFORE the LLM validator runs.
# Deterministic and free — the LLM only adjudicates near-misses.
# ============================================================

def _normalize(text: str) -> str:
    """Collapse whitespace and lowercase for tolerant substring matching."""
    return " ".join(text.lower().split())


def verify_citations_mechanically(
    findings: List[dict],
    chunks:   List[dict],
) -> dict:
    """
    Check every Citation.verbatim_quote against retrieved chunk contents.
    Returns per-finding grounding counts and an overall summary:
      {"findings": {finding_id: {"verified": n, "unverified": n,
                                 "unverified_quotes": [...]}},
       "total_verified": n, "total_unverified": n}
    """
    corpus_text = _normalize(" ".join(str(c.get("content", "")) for c in chunks))

    result: dict = {"findings": {}, "total_verified": 0, "total_unverified": 0}

    for f in findings:
        fid = f.get("finding_id", "?")
        verified, unverified, missing = 0, 0, []
        citations = list(f.get("source_provisions", [])) + list(
            f.get("overlapping_provisions", [])
        )
        for c in citations:
            quote = c.get("verbatim_quote", "") if isinstance(c, dict) else str(c)
            if quote and _normalize(quote) in corpus_text:
                verified += 1
            else:
                unverified += 1
                missing.append(quote[:120])
        result["findings"][fid] = {
            "verified":          verified,
            "unverified":        unverified,
            "unverified_quotes": missing,
        }
        result["total_verified"]   += verified
        result["total_unverified"] += unverified

    return result


def check_source_independence(findings: List[dict], chunks: List[dict]) -> dict:
    """
    Quality goal 1.3 (source independence): a HORIZONTAL sludge finding claims
    an overlap/conflict BETWEEN two instruments — that claim is only evidenced
    if source_provisions and overlapping_provisions trace to at least two
    distinct documents. A finding citing the same document for "source" and
    "overlap" has not actually shown a cross-instrument conflict, regardless of
    how confident the model sounds or whether the quotes verify verbatim.
    Deterministic and free — traces each citation's chunk_uid to document_uid
    via the retrieved chunks (not just document_title, which can collide).

    Returns {finding_id: {"sludge_type", "distinct_documents", "independent"}}
    for horizontal findings only (vertical/cumulative are not covered by this
    goal — they legitimately span layers of one regulatory stack, not two
    parallel bodies).
    """
    chunk_to_doc = {
        str(c.get("chunk_uid")): str(c.get("document_uid")) for c in chunks
    }

    result: dict = {}
    for f in findings:
        if f.get("sludge_type") != "horizontal":
            continue
        fid = f.get("finding_id", "?")
        citations = list(f.get("source_provisions", [])) + list(
            f.get("overlapping_provisions", [])
        )
        docs = set()
        for c in citations:
            uid = c.get("chunk_uid") if isinstance(c, dict) else None
            doc = chunk_to_doc.get(str(uid))
            if doc and doc != "None":
                docs.add(doc)
        result[fid] = {
            "sludge_type":         "horizontal",
            "distinct_documents":  len(docs),
            "independent":         len(docs) >= 2,
        }
    return result


def grounded_confidence(finding: dict, grounding: dict) -> float:
    """
    Evidence-based confidence: verified citations / total citations,
    capped by the model's self-reported score. Zero citations = 0.0.
    """
    g = grounding.get("findings", {}).get(finding.get("finding_id", "?"), {})
    total = g.get("verified", 0) + g.get("unverified", 0)
    if total == 0:
        return 0.0
    evidence_score = g.get("verified", 0) / total
    self_score     = float(finding.get("confidence_score", 1.0))
    return round(min(evidence_score, self_score), 2)
