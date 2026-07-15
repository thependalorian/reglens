from __future__ import annotations
from pydantic_ai import Agent, RunContext
from agent.providers import get_llm_model
from agent.models import SludgeAnalysis, CitationValidation
from agent.prompts import (
    build_detection_prompt,
    build_citation_validator_prompt,
    build_report_prompt,
)
from agent.tools import AgentDeps, hybrid_search, format_chunks_for_agent


# ============================================================
# Agent 1: Sludge Detector
# Capable model — this is the core analytical workload
# system_prompt built dynamically from corpus_map
# ============================================================

sludge_detector = Agent(
    get_llm_model(use_capable=True),
    deps_type=AgentDeps,
    output_type=SludgeAnalysis,
    model_settings={"temperature": 0.0},
)


def _accumulate_chunks(deps: AgentDeps, chunks: list) -> None:
    """Accumulate retrieved chunks across tool calls, deduped by chunk_uid.
    Enables honest coverage reporting: everything the agent saw is tracked."""
    seen = {str(c.get("chunk_uid")) for c in deps.retrieved_chunks}
    deps.retrieved_chunks = deps.retrieved_chunks + [
        c for c in chunks if str(c.get("chunk_uid")) not in seen
    ]


@sludge_detector.system_prompt
def detector_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return build_detection_prompt(ctx.deps.corpus_map)


@sludge_detector.tool
async def retrieve_regulatory_documents(
    ctx:          RunContext[AgentDeps],
    search_query: str,
    focus_area:   str = "",
) -> str:
    """
    Retrieve relevant regulatory provisions using hybrid search.
    Searches the entire corpus — no jurisdiction filtering.
    Args:
        search_query: Topic or obligation to search for
        focus_area:   Optional narrowing term (e.g. 'reporting frequency', 'capital buffer')
    """
    combined = f"{search_query} {focus_area}".strip()
    chunks   = await hybrid_search(
        ctx.deps.pool,
        ctx.deps.embedding_client,
        combined,
        match_count=20,
    )
    _accumulate_chunks(ctx.deps, chunks)
    return format_chunks_for_agent(chunks)


@sludge_detector.tool
async def search_for_specific_provision(
    ctx:                 RunContext[AgentDeps],
    provision_reference: str,
) -> str:
    """
    Targeted search for a specific regulatory provision or article.
    Use to verify a citation before including it in a finding.
    Args:
        provision_reference: e.g. 'Article 9(1) EMIR reporting obligation'
    """
    chunks = await hybrid_search(
        ctx.deps.pool,
        ctx.deps.embedding_client,
        provision_reference,
        match_count=5,
    )
    if not chunks:
        return (
            f"NOT FOUND: '{provision_reference}' — "
            f"not in corpus. Do not cite this provision."
        )
    _accumulate_chunks(ctx.deps, chunks)
    return format_chunks_for_agent(chunks)


# ============================================================
# Agent 2: Citation Validator (Guardrail)
# Capable model — legal accuracy is high stakes
# ============================================================

citation_validator = Agent(
    get_llm_model(use_capable=True),
    deps_type=AgentDeps,
    output_type=CitationValidation,
    system_prompt=build_citation_validator_prompt(),
    model_settings={"temperature": 0.0},
)


@citation_validator.tool
async def verify_provision_in_corpus(
    ctx:              RunContext[AgentDeps],
    source_reference: str,
) -> str:
    """
    Search corpus for a specific cited provision to verify existence.
    Args:
        source_reference: The exact citation to verify
    """
    chunks = await hybrid_search(
        ctx.deps.pool,
        ctx.deps.embedding_client,
        source_reference,
        match_count=5,
    )
    if not chunks:
        return f"NOT FOUND: '{source_reference}' could not be verified in corpus."
    return format_chunks_for_agent(chunks)


# ============================================================
# Agent 3: Report Generator
# Capable model — final synthesis
# system_prompt built dynamically from corpus_map
# ============================================================

report_generator = Agent(
    get_llm_model(use_capable=True),
    deps_type=AgentDeps,
    model_settings={"temperature": 0.2},
)


@report_generator.system_prompt
def report_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return build_report_prompt(ctx.deps.corpus_map)