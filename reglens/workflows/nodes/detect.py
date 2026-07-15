from __future__ import annotations
import asyncio
from typing import Optional, Callable, List

from workflows.state import SludgeWorkflowState
from agent.agent import sludge_detector
from agent.tools import (
    AgentDeps,
    verify_citations_mechanically,
    grounded_confidence,
)
from agent.clients import get_pg_pool, get_embedding_client, get_llm_client

AGENT_TIMEOUT_SECONDS = 180

_OBLIGATION_DIGEST_PROMPT = (
    "Extract every distinct regulatory obligation from this document excerpt. "
    "One line each: WHO must do WHAT, citing the section/article if visible. "
    "Only what the text states — no interpretation. Respond as a plain list."
)


async def _exhaustive_digest(chunks: List[dict], writer: Optional[Callable]) -> str:
    """
    Map step of exhaustive mode: mini-model obligation extraction per
    document, so the detector can synthesize across the WHOLE corpus
    instead of top-k retrieval. One mini call per document.
    """
    by_doc: dict = {}
    for c in chunks:
        by_doc.setdefault(c.get("document_title", "Unknown"), []).append(
            str(c.get("content", ""))
        )

    client = get_llm_client()
    import os
    mini = os.getenv("LLM_CHOICE", "gpt-4o-mini")

    digests = []
    for i, (title, texts) in enumerate(sorted(by_doc.items()), 1):
        if writer:
            writer(f"*[exhaustive] digesting {i}/{len(by_doc)}: {title[:60]}*\n")
        body = "\n\n".join(texts)[:24000]
        try:
            resp = await client.chat.completions.create(
                model=mini,
                messages=[{
                    "role": "user",
                    "content": f"{_OBLIGATION_DIGEST_PROMPT}\n\nDOCUMENT: {title}\n\n{body}",
                }],
                max_tokens=800,
                temperature=0.0,
            )
            digests.append(f"### {title}\n{resp.choices[0].message.content or ''}")
        except Exception as e:
            digests.append(f"### {title}\n[digest failed: {e}]")

    return "\n\n".join(digests)


async def detect_node(
    state:  SludgeWorkflowState,
    writer: Optional[Callable] = None,
) -> dict:
    iteration  = state.get("iteration_count", 0)
    feedback   = state.get("validation_feedback", "")
    exhaustive = state.get("exhaustive", False)

    if writer:
        label = "Re-analyzing with validator feedback" if iteration > 0 else "Analyzing for policy sludge"
        writer(f"\n**[3/5] {label} (iteration {iteration + 1}/3)...**\n")
        if feedback:
            writer(f"*Validator feedback: {feedback[:200]}*\n")

    try:
        deps = AgentDeps(
            pool=             await get_pg_pool(),
            embedding_client= get_embedding_client(),
            corpus_map=       state.get("corpus_map", {}),
            retrieved_chunks= list(state.get("retrieved_chunks", [])),
        )

        query = state.get("query", "")

        if exhaustive and iteration == 0:
            digest = await _exhaustive_digest(deps.retrieved_chunks, writer)
            query = (
                f"{query}\n\n"
                f"EXHAUSTIVE MODE: the obligation digest below covers EVERY document "
                f"in the corpus. Cross-reference it for overlaps and conflicts, then "
                f"use your retrieval tools to pull the exact provisions you cite.\n\n"
                f"{digest}"
            )

        if feedback:
            query = (
                f"{query}\n\n"
                f"VALIDATOR FEEDBACK — correct these issues in your findings:\n{feedback}"
            )

        async with asyncio.timeout(AGENT_TIMEOUT_SECONDS):
            result = await sludge_detector.run(
                query,
                deps=deps,
                message_history=state.get("pydantic_message_history", []),
            )

        analysis      = result.output
        findings_json = [f.model_dump() for f in analysis.findings]

        # Ground truth from the environment: verify every verbatim quote
        # against the retrieved chunks, then recompute confidence from
        # verified evidence (never trust the model's self-report alone).
        grounding = verify_citations_mechanically(findings_json, deps.retrieved_chunks)
        for f in findings_json:
            f["confidence_score"] = grounded_confidence(f, grounding)

        # Coverage disclosure — what was actually examined
        examined_titles = sorted({
            str(c.get("document_title", "Unknown")) for c in deps.retrieved_chunks
        })
        corpus_map = state.get("corpus_map", {})
        coverage = {
            "documents_examined": examined_titles,
            "chunks_examined":    len(deps.retrieved_chunks),
            "corpus_documents":   corpus_map.get("document_count", 0),
            "corpus_chunks":      corpus_map.get("corpus_chunk_count", 0),
            "mode":               "exhaustive" if exhaustive else "retrieval",
        }

        if writer:
            writer(
                f"\n*Found {analysis.total_findings} findings "
                f"({analysis.high_severity_count} high severity) | "
                f"citations verified={grounding['total_verified']} "
                f"unverified={grounding['total_unverified']} | "
                f"coverage={len(examined_titles)}/{coverage['corpus_documents']} documents*\n"
            )

        return {
            "sludge_findings":           findings_json,
            "detection_summary":         analysis.summary,
            "grounding":                 grounding,
            "coverage":                  coverage,
            "retrieved_chunks":          deps.retrieved_chunks,
            "pydantic_message_history":  result.all_messages(),
            "message_history":           [result.new_messages_json()],
            "status":                    "detected",
            "work_log": [
                f"[detect] findings={analysis.total_findings} "
                f"high={analysis.high_severity_count} "
                f"verified={grounding['total_verified']} "
                f"unverified={grounding['total_unverified']} "
                f"coverage={len(examined_titles)}/{coverage['corpus_documents']}docs "
                f"iteration={iteration + 1}"
            ],
        }
    except Exception as e:
        return {
            "status":        "error",
            "error_message": str(e),
            "work_log":      [f"[detect] ERROR: {e}"],
        }
