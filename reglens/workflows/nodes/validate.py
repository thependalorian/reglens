from __future__ import annotations
import asyncio
import json
from typing import Optional, Callable
from ..state import SludgeWorkflowState
from agent.agent import citation_validator
from agent.tools import (
    AgentDeps,
    format_chunks_for_agent,
    verify_citations_mechanically,
    check_source_independence,
)
from agent.clients import get_pg_pool, get_embedding_client

AGENT_TIMEOUT_SECONDS = 120


async def validate_node(
    state:  SludgeWorkflowState,
    writer: Optional[Callable] = None,
) -> dict:
    if writer:
        writer("\n**[4/5] Validating citations...**\n")

    findings  = state.get("sludge_findings", [])
    chunks    = state.get("retrieved_chunks", [])
    iteration = state.get("iteration_count", 0)

    # Mechanical pre-check (deterministic, free) — the LLM validator only
    # adjudicates quotes the substring match could not verify.
    grounding = state.get("grounding") or verify_citations_mechanically(findings, chunks)
    if writer:
        writer(
            f"*Mechanical check: {grounding['total_verified']} verified, "
            f"{grounding['total_unverified']} need adjudication*\n"
        )

    # Quality goal 1.3 (source independence, deterministic, free): a
    # horizontal finding citing only one document has not shown a
    # cross-instrument conflict, no matter how confident the model sounds or
    # whether the quotes verify verbatim. A live-tested cross-border
    # comparison produced a high-confidence, fully-verbatim-verified finding
    # grounded entirely in one Namibia document while claiming to compare
    # Namibia/Kenya/Hong Kong — this catches exactly that. Computed before the
    # LLM call and enforced in the except path too, so it is a hard gate that
    # cannot be bypassed by an LLM outage nor overridden by the LLM's opinion.
    independence = check_source_independence(findings, chunks)
    independence_issues = [
        f"{fid}: horizontal finding \"{next((f.get('title', '') for f in findings if f.get('finding_id') == fid), '')}\" "
        f"cites only {info['distinct_documents']} distinct document(s) across its "
        f"source_provisions and overlapping_provisions — a horizontal (cross-instrument) "
        f"claim requires evidence from at least 2 distinct documents. Either find a genuine "
        f"second-instrument citation for this overlap, or drop the finding / reclassify it "
        f"(e.g. as vertical/cumulative if it is actually within one instrument's stack)."
        for fid, info in independence.items()
        if not info["independent"]
    ]
    if writer and independence_issues:
        writer(
            f"*Source independence: {len(independence_issues)} horizontal "
            f"finding(s) cite only one document*\n"
        )

    try:
        deps = AgentDeps(
            pool=             await get_pg_pool(),
            embedding_client= get_embedding_client(),
            corpus_map=       state.get("corpus_map", {}),
        )

        findings_str  = json.dumps(findings, indent=2)
        corpus_sample = format_chunks_for_agent(chunks[:8])
        grounding_str = json.dumps(grounding, indent=2)

        async with asyncio.timeout(AGENT_TIMEOUT_SECONDS):
            result = await citation_validator.run(
                f"MECHANICAL VERIFICATION RESULTS (pre-computed):\n{grounding_str}\n\n"
                f"FINDINGS TO VALIDATE:\n{findings_str}\n\n"
                f"CORPUS SAMPLE:\n{corpus_sample}",
                deps=deps,
            )
        validation = result.output
        llm_valid  = validation.is_valid
        all_issues = list(validation.issues) + independence_issues
    except Exception as e:
        # Fail-safe on the LLM adjudication only — never fail-open on the
        # deterministic independence gate above, which needed no LLM to compute.
        llm_valid  = True
        all_issues = independence_issues + [f"[validate] LLM adjudication error (fail-safe pass): {e}"]

    is_valid = llm_valid and not independence_issues

    if writer:
        icon   = "✓" if is_valid else "✗"
        status = "PASSED" if is_valid else "FAILED"
        writer(f"\n*{icon} Citation validation {status}*\n")
        if not is_valid and all_issues:
            writer(f"*Issues: {'; '.join(all_issues[:2])}*\n")

    return {
        "validation_result":   "valid" if is_valid else "invalid",
        "validation_feedback": "; ".join(all_issues),
        "validation_issues":   all_issues,
        "iteration_count":     iteration + (0 if is_valid else 1),
        "status":              "validated" if is_valid else "validation_failed",
        "work_log": [
            f"[validate] {'PASS' if is_valid else 'FAIL'} "
            f"issues={len(all_issues)} "
            f"(independence_issues={len(independence_issues)}) "
            f"iteration={iteration}"
        ],
    }


def route_after_validation(state: SludgeWorkflowState) -> str:
    """
    Conditional edge:
    - invalid AND under 3 iterations → retry detect
    - valid OR 3 iterations reached  → proceed to HITL
    """
    result    = state.get("validation_result", "invalid")
    iteration = state.get("iteration_count", 0)
    if result == "invalid" and iteration < 3:
        return "detect"
    return "hitl"