from __future__ import annotations
import os
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import SludgeWorkflowState
from .nodes.discovery import discover_node
from .nodes.retrieve  import retrieve_node
from .nodes.detect    import detect_node
from .nodes.validate  import validate_node, route_after_validation
from .nodes.hitl      import hitl_node, route_after_hitl
from .nodes.report    import report_node


async def _fallback_de(state: SludgeWorkflowState, writer=None) -> dict:
    if writer:
        writer(
            "\n*Max validation iterations reached. "
            "Returning preliminary findings — expert review required.*\n"
        )
    return {
        "final_report": (
            f"## PRELIMINARY FINDINGS (Unvalidated — "
            f"{state.get('iteration_count', 0)} attempts)\n\n"
            f"{state.get('detection_summary', '')}\n\n"
            f"*Citation validation could not be fully completed. "
            f"All findings require expert review before action.*"
        ),
        "workflow_complete": True,
        "status":            "fallback_complete",
        "work_log":          ["[fallback] Max iterations — preliminary report"],
    }


def build_graph(checkpointer=None):
    builder = StateGraph(SludgeWorkflowState)

    builder.add_node("discover",  discover_node)
    builder.add_node("retrieve",  retrieve_node)
    builder.add_node("detect",    detect_node)
    builder.add_node("validate",  validate_node)
    builder.add_node("hitl",      hitl_node)
    builder.add_node("report",    report_node)
    builder.add_node("fallback",  _fallback_de)

    builder.add_edge(START,      "discover")
    builder.add_edge("discover", "retrieve")
    builder.add_edge("retrieve", "detect")
    builder.add_edge("detect",   "validate")

    builder.add_conditional_edges(
        "validate",
        route_after_validation,
        {"detect": "detect", "hitl": "hitl"},
    )
    builder.add_conditional_edges(
        "hitl",
        route_after_hitl,
        {"report": "report", "hitl": "hitl", "end": END},
    )

    builder.add_edge("report",   END)
    builder.add_edge("fallback", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())


async def _build_postgres_saver():
    """
    Persistent AsyncPostgresSaver on the Neon DIRECT endpoint.

    Two requirements meet here:
    - ag_ui_langgraph time-travel needs a persistent checkpointer (MemorySaver
      loses history on restart -> 'Message ID not found in history').
    - The checkpointer holds one connection across the multi-minute
      detect/validate LLM calls and the HITL wait. On Neon's -pooler
      (PgBouncer) endpoint that idle-but-held connection is killed, surfacing
      as 'SSL SYSCALL error: EOF detected' at aput_writes. Use the DIRECT
      endpoint (strip '-pooler.') plus TCP keepalives so it survives long runs.
    """
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        return None
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    checkpointer_dsn = dsn.replace("-pooler.", ".")  # Neon direct endpoint
    pool = AsyncConnectionPool(
        conninfo=checkpointer_dsn,
        max_size=4,
        open=False,
        check=AsyncConnectionPool.check_connection,
        max_idle=30,
        max_lifetime=300,
        kwargs={
            "autocommit":        True,
            "prepare_threshold": None,
            "row_factory":       dict_row,
            "keepalives":          1,
            "keepalives_idle":     15,
            "keepalives_interval": 10,
            "keepalives_count":    3,
        },
    )
    await pool.open()
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    return saver


# Module-level workflow — MemorySaver for import-time safety.
# Use create_workflow() (from the FastAPI lifespan) for production instances.
workflow = build_graph(MemorySaver())


async def create_workflow():
    """
    Create the workflow with a persistent checkpointer for production.
    Falls back to MemorySaver when DATABASE_URL is unset or the saver cannot
    be built (dev only — time-travel will not persist across restarts).
    """
    if os.getenv("DATABASE_URL") and os.getenv(
        "USE_POSTGRES_CHECKPOINTER", "true"
    ).lower() == "true":
        try:
            saver = await _build_postgres_saver()
            if saver is not None:
                return build_graph(saver)
        except Exception as e:
            print(f"[graph] Postgres checkpointer unavailable ({e}) — using MemorySaver")
    return build_graph(MemorySaver())


def create_initial_state(
    query:      str,
    session_id: str,
    request_id: str,
    user_uid:   str = "",
    exhaustive: bool = False,
    history=None,
) -> SludgeWorkflowState:
    return {
        "query":                     query,
        "session_id":                session_id,
        "request_id":                request_id,
        "user_uid":                  user_uid,
        "exhaustive":                exhaustive,
        "messages":                  [],      # required for ag_ui_langgraph
        "iteration_count":           0,
        "approval_status":           "pending",
        "workflow_complete":         False,
        "work_log":                  [],
        "pydantic_message_history":  history or [],
        "message_history":           [],
    }