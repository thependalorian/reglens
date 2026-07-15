"""
Pre-rulemaking check node.
Compares a draft regulatory document against the existing corpus.
Enables the Policy & Regulation use case without modifying the main workflow.
"""
from __future__ import annotations
import asyncio
import json
from typing import Optional, Callable
from pydantic_ai import Agent, RunContext
from agent.providers import get_llm_model
from agent.tools import AgentDeps, hybrid_search, format_chunks_for_agent
from agent.clients import get_pg_pool, get_embedding_client
from agent.prompts import PRE_RULEMAKING_CHECK_PROMPT
from agent.models import SludgeAnalysis


# Pre-rulemaking check agent
# Uses the same SludgeAnalysis output type — findings = conflicts with existing corpus
precheck_agent = Agent(
    get_llm_model(use_capable=True),
    deps_type=AgentDeps,
    output_type=SludgeAnalysis,
    model_settings={"temperature": 0.0},
)


@precheck_agent.system_prompt
def precheck_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    # .replace, not .format — the prompt embeds JSON brace examples
    return PRE_RULEMAKING_CHECK_PROMPT.replace(
        "{corpus_profile}", json.dumps(ctx.deps.corpus_map, indent=2)
    )


@precheck_agent.tool
async def search_existing_corpus(
    ctx:          RunContext[AgentDeps],
    search_query: str,
) -> str:
    """
    Search the EXISTING regulatory corpus for provisions relevant to the draft.
    Use this to find obligations the draft may be duplicating or conflicting with.
    """
    chunks = await hybrid_search(
        ctx.deps.pool,
        ctx.deps.embedding_client,
        search_query,
        match_count=10,
    )
    from agent.agent import _accumulate_chunks
    _accumulate_chunks(ctx.deps, chunks)
    return format_chunks_for_agent(chunks)


async def precheck_node(
    draft_title: str,
    draft_text:  str,
    corpus_map:  dict,
    writer:      Optional[Callable] = None,
) -> dict:
    """
    Run pre-rulemaking check: compare draft against existing corpus.
    Returns sludge findings representing conflicts/overlaps.
    """
    if writer:
        writer(f"\n**Pre-rulemaking Check: '{draft_title}'**\n")
        writer("*Comparing draft against existing corpus...*\n")

    deps = AgentDeps(
        pool=             await get_pg_pool(),
        embedding_client= get_embedding_client(),
        corpus_map=       corpus_map,
    )

    query = (
        f"Pre-rulemaking check for: '{draft_title}'\n\n"
        f"DRAFT TEXT:\n{draft_text[:6000]}\n\n"
        f"Find conflicts, duplications, and accumulation risks between this draft "
        f"and the existing regulatory corpus."
    )

    async with asyncio.timeout(180):
        result = await precheck_agent.run(query, deps=deps)
    analysis = result.output

    if writer:
        writer(
            f"\n*Found {analysis.total_findings} conflicts "
            f"({analysis.high_severity_count} high priority) | "
            f"confidence={analysis.confidence_score:.2f}*\n"
        )

    return {
        "findings":          [f.model_dump() for f in analysis.findings],
        "summary":           analysis.summary,
        "total_conflicts":   analysis.total_findings,
        "high_priority":     analysis.high_severity_count,
        "confidence_score":  analysis.confidence_score,
    }
