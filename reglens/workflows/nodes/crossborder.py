"""
Cross-border gap analysis node.
Compares two regulatory frameworks on the same topic.
Enables the Cross-regulatory & Cross-border Collaboration use case.
"""
from __future__ import annotations
import asyncio
import json
from typing import Optional, Callable, List
from pydantic_ai import Agent, RunContext
from agent.providers import get_llm_model
from agent.tools import AgentDeps, hybrid_search, format_chunks_for_agent
from agent.clients import get_pg_pool, get_embedding_client
from agent.prompts import CROSS_BORDER_ANALYSIS_PROMPT
from agent.models import CrossBorderAnalysis


# Cross-border comparison agent
crossborder_agent = Agent(
    get_llm_model(use_capable=True),
    deps_type=AgentDeps,
    output_type=CrossBorderAnalysis,
    model_settings={"temperature": 0.0},
)


@crossborder_agent.system_prompt
def crossborder_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    # .replace, not .format — the prompt embeds JSON brace examples
    return (
        CROSS_BORDER_ANALYSIS_PROMPT
        .replace("{label_a}", ctx.deps.corpus_map.get("label_a", "Framework A"))
        .replace("{label_b}", ctx.deps.corpus_map.get("label_b", "Framework B"))
        .replace("{topic}",   ctx.deps.corpus_map.get("topic", "regulatory obligations"))
        .replace("{corpus_profile}", json.dumps(ctx.deps.corpus_map, indent=2))
    )


@crossborder_agent.tool
async def retrieve_framework_a_provisions(
    ctx:          RunContext[AgentDeps],
    search_query: str,
) -> str:
    """
    Retrieve provisions from Framework A matching the query.
    """
    filter_a = ctx.deps.corpus_map.get("filter_a", {})
    chunks   = await _filtered_search(ctx, search_query, filter_a)
    return f"[FRAMEWORK A]\n{format_chunks_for_agent(chunks)}"


@crossborder_agent.tool
async def retrieve_framework_b_provisions(
    ctx:          RunContext[AgentDeps],
    search_query: str,
) -> str:
    """
    Retrieve provisions from Framework B matching the query.
    """
    filter_b = ctx.deps.corpus_map.get("filter_b", {})
    chunks   = await _filtered_search(ctx, search_query, filter_b)
    return f"[FRAMEWORK B]\n{format_chunks_for_agent(chunks)}"


async def _filtered_search(
    ctx:     RunContext[AgentDeps],
    query:   str,
    filter_: dict,
) -> List[dict]:
    """Search corpus then apply client-side metadata filter."""
    chunks = await hybrid_search(
        ctx.deps.pool,
        ctx.deps.embedding_client,
        query,
        match_count=15,
    )
    if filter_:
        def matches(c: dict) -> bool:
            meta = c.get("document_metadata") or {}
            return all(
                str(meta.get(k, "")).lower() == str(v).lower()
                for k, v in filter_.items() if v
            )
        chunks = [c for c in chunks if matches(c)]
    return chunks[:8]


async def crossborder_node(
    label_a:    str,
    label_b:    str,
    filter_a:   dict,
    filter_b:   dict,
    topic:      str,
    corpus_map: dict,
    writer:     Optional[Callable] = None,
) -> dict:
    """
    Run cross-border gap analysis between two regulatory frameworks.
    Returns gaps, harmonisation score, and coordination recommendations.
    """
    if writer:
        writer(f"\n**Cross-Border Analysis: {label_a} vs {label_b}**\n")
        writer(f"*Topic: {topic}*\n")
        writer("*Retrieving and comparing frameworks...*\n")

    # Extend corpus_map with comparison context
    comparison_corpus_map = {
        **corpus_map,
        "label_a":  label_a,
        "label_b":  label_b,
        "topic":    topic,
        "filter_a": filter_a,
        "filter_b": filter_b,
    }

    deps = AgentDeps(
        pool=             await get_pg_pool(),
        embedding_client= get_embedding_client(),
        corpus_map=       comparison_corpus_map,
    )

    query = (
        f"Perform a comprehensive cross-border gap analysis.\n"
        f"Framework A: {label_a}\n"
        f"Framework B: {label_b}\n"
        f"Topic: {topic}\n\n"
        f"Use the retrieval tools to get relevant provisions from each framework. "
        f"Identify all gaps, divergences, and harmonisation opportunities. "
        f"Provide a harmonisation score and concrete coordination recommendations."
    )

    async with asyncio.timeout(180):
        result = await crossborder_agent.run(query, deps=deps)
    analysis = result.output

    if writer:
        writer(
            f"\n*Found {analysis.total_gaps} gaps | "
            f"Harmonisation score: {analysis.harmonisation_score:.2f} | "
            f"Key friction points: {len(analysis.key_friction_points)}*\n"
        )

    return analysis.model_dump()
