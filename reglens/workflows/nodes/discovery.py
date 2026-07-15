"""
Corpus discovery node — runs before detection.
Builds corpus_map from document metadata in DB.
No LLM call, no hardcoded assumptions — pure DB aggregation.
This is the key to adaptivity: the system learns what it has before analyzing it.
"""
from __future__ import annotations
from typing import Optional, Callable
from workflows.state import SludgeWorkflowState
from agent.tools import discover_corpus_map
from agent.clients import get_pg_pool


async def discover_node(
    state:  SludgeWorkflowState,
    writer: Optional[Callable] = None,
) -> dict:
    if writer:
        writer("\n**[1/5] Discovering corpus...**\n")

    try:
        corpus_map = await discover_corpus_map(await get_pg_pool())

        if writer:
            writer(
                f"*Corpus: {corpus_map['document_count']} documents | "
                f"Bodies: {', '.join(corpus_map['regulatory_bodies'][:3])} | "
                f"Domains: {', '.join(corpus_map['domains'][:3])}*\n"
            )

        return {
            "corpus_map": corpus_map,
            "status":     "discovered",
            "work_log":   [
                f"[discover] {corpus_map['coverage_summary']}"
            ],
        }
    except Exception as e:
        return {
            "corpus_map":  {"document_count": 0, "regulatory_bodies": [], "domains": [],
                            "document_types": [], "regulatory_levels": [], "coverage_summary": "unknown"},
            "status":      "discover_error",
            "work_log":    [f"[discover] ERROR: {e}"],
        }