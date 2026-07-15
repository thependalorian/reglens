from __future__ import annotations
from typing import Optional, Callable
from workflows.state import SludgeWorkflowState
from agent.tools import hybrid_search, fetch_all_chunks
from agent.clients import get_pg_pool, get_embedding_client


async def retrieve_node(
    state:  SludgeWorkflowState,
    writer: Optional[Callable] = None,
) -> dict:
    exhaustive = state.get("exhaustive", False)

    if writer:
        label = "Loading full corpus (exhaustive mode)" if exhaustive \
            else "Retrieving regulatory documents"
        writer(f"\n**[2/5] {label}...**\n")

    try:
        pool = await get_pg_pool()

        if exhaustive:
            # Full-corpus sweep: every active chunk, no embedding search
            chunks = await fetch_all_chunks(pool)
        else:
            chunks = await hybrid_search(
                pool,
                get_embedding_client(),
                state.get("query", ""),
                match_count=24,
            )

        if writer:
            writer(f"*Retrieved {len(chunks)} relevant chunks*\n")

        return {
            "retrieved_chunks": chunks,
            "status":           "retrieved",
            "work_log":         [
                f"[retrieve] {len(chunks)} chunks | "
                f"{'exhaustive' if exhaustive else 'hybrid'} | "
                f"query='{state.get('query', '')[:60]}'"
            ],
        }
    except Exception as e:
        return {
            "retrieved_chunks": [],
            "status":           "error",
            "error_message":    str(e),
            "work_log":         [f"[retrieve] ERROR: {e}"],
        }
