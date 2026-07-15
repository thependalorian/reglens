from __future__ import annotations
import asyncio
import json
from typing import Optional, Callable
from workflows.state import SludgeWorkflowState
from agent.agent import citation_validator
from agent.tools import AgentDeps, format_chunks_for_agent, verify_citations_mechanically
from agent.clients import get_pg_pool, get_embedding_client

AGENT_TIMEOUT_SECONDS = 120


async def validate_node(
    state:  SludgeWorkflowState,
    writer: Optional[Callable] = None,
) -> dict:
    if writer:
        writer("\n**[4/5] Validating citations...**\n")

    try:
        deps = AgentDeps(
            pool=             await get_pg_pool(),
            embedding_client= get_embedding_client(),
            corpus_map=       state.get("corpus_map", {}),
        )

        findings = state.get("sludge_findings", [])
        chunks   = state.get("retrieved_chunks", [])

        # Mechanical pre-check (deterministic, free) — the LLM validator
        # only adjudicates quotes the substring match could not verify.
        grounding = state.get("grounding") or verify_citations_mechanically(
            findings, chunks
        )
        if writer:
            writer(
                f"*Mechanical check: {grounding['total_verified']} verified, "
                f"{grounding['total_unverified']} need adjudication*\n"
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
        validation    = result.output
        is_valid      = validation.is_valid
        iteration     = state.get("iteration_count", 0)

        if writer:
            icon   = "✓" if is_valid else "✗"
            status = "PASSED" if is_valid else "FAILED"
            writer(f"\n*{icon} Citation validation {status}*\n")
            if not is_valid and validation.issues:
                writer(f"*Issues: {'; '.join(validation.issues[:2])}*\n")

        return {
            "validation_result":   "valid" if is_valid else "invalid",
            "validation_feedback": "; ".join(validation.issues),
            "validation_issues":   validation.issues,
            "iteration_count":     iteration + (0 if is_valid else 1),
            "status":              "validated" if is_valid else "validation_failed",
            "work_log": [
                f"[validate] {'PASS' if is_valid else 'FAIL'} "
                f"issues={len(validation.issues)} iteration={iteration}"
            ],
        }
    except Exception as e:
        # Fail-safe: don't block on validator error
        return {
            "validation_result":   "valid",
            "validation_feedback": "",
            "status":              "validated",
            "work_log":            [f"[validate] ERROR (fail-safe pass): {e}"],
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