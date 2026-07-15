from __future__ import annotations
import os
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from workflows.state import SludgeWorkflowState
from workflows.nodes.triage    import triage_node, route_after_triage
from workflows.nodes.discovery import discover_node
from workflows.nodes.retrieve  import retrieve_node
from workflows.nodes.detect    import detect_node
from workflows.nodes.validate  import validate_node, route_after_validation
from workflows.nodes.hitl      import hitl_node, route_after_hitl
from workflows.nodes.report    import report_node


async def _fallback_node(state: SludgeWorkflowState, writer=None) -> dict:
    """Returns preliminary findings when max validation iterations reached."""
    if writer:
        writer(
            "\n*Max validation iterations reached. "
            "Returning preliminary findings — expert review strongly recommended.*\n"
        )
    return {
        "final_report": (
            f"## PRELIMINARY FINDINGS (Unvalidated — {state.get('iteration_count', 0)} attempts)\n\n"
            f"{state.get('detection_summary', '')}\n\n"
            f"*Citation validation could not be fully completed. "
            f"All findings require expert review before action.*"
        ),
        "workflow_complete": True,
        "status":            "fallback_complete",
        "work_log": ["[fallback] Max iterations — preliminary report returned"],
    }


def create_workflow(checkpointer=None):
    builder = StateGraph(SludgeWorkflowState)

    # Nodes
    builder.add_node("triage",    triage_node)
    builder.add_node("discover",  discover_node)
    builder.add_node("retrieve",  retrieve_node)
    builder.add_node("detect",    detect_node)
    builder.add_node("validate",  validate_node)
    builder.add_node("hitl",      hitl_node)
    builder.add_node("report",    report_node)
    builder.add_node("fallback",  _fallback_node)

    # Intent gate: casual/off-topic/unanswerable inputs never reach retrieval
    builder.add_edge(START, "triage")
    builder.add_conditional_edges(
        "triage",
        route_after_triage,
        {"discover": "discover", "end": END},
    )

    # Fixed edges
    builder.add_edge("discover", "retrieve")
    builder.add_edge("retrieve", "detect")
    builder.add_edge("detect",   "validate")

    # Guardrail loop: valid/max → HITL, invalid (<3) → detect
    builder.add_conditional_edges(
        "validate",
        route_after_validation,
        {"detect": "detect", "hitl": "hitl"},
    )

    # HITL gate: approved → report, rejected → END,
    # refine → back to retrieve with reviewer feedback (and optionally
    # exhaustive retrieval) for another detection pass.
    # The pause itself is a dynamic interrupt() inside hitl_node.
    builder.add_conditional_edges(
        "hitl",
        route_after_hitl,
        {"report": "report", "end": END, "retrieve": "retrieve"},
    )

    builder.add_edge("report",   END)
    builder.add_edge("fallback", END)

    # The HITL pause is a dynamic interrupt() inside hitl_node — the
    # graph checkpoints there and resumes with Command(resume=decision).
    return builder.compile(checkpointer=checkpointer or MemorySaver())


async def create_postgres_checkpointer():
    """
    Postgres checkpointer on DATABASE_URL so HITL state survives restarts.
    Returns None (caller falls back to MemorySaver) when unavailable.
    """
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        return None
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        # Neon's -pooler (PgBouncer) endpoint kills a connection that sits idle
        # while it is checked out — which is exactly what the LangGraph
        # checkpointer does: it holds one connection across the multi-minute
        # detect/validate LLM calls, then writes at the HITL interrupt. The
        # pooler drop surfaces as "SSL SYSCALL error: EOF detected" at
        # aput_writes, and check_connection cannot help because it only runs at
        # checkout, not on an already-held connection. Use Neon's DIRECT
        # endpoint for this long-held connection (the app's short-lived query
        # pool can stay on the pooler).
        checkpointer_dsn = dsn.replace("-pooler.", ".")

        pool = AsyncConnectionPool(
            conninfo=checkpointer_dsn,
            max_size=4,
            open=False,
            # Belt and braces on the direct endpoint too: revalidate on
            # checkout, recycle idle connections inside Neon's idle window,
            # cap lifetime, and keep the socket warm with TCP keepalives so it
            # is not seen as idle during a slow validation loop or HITL wait.
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
    except Exception as e:
        print(f"[graph] Postgres checkpointer unavailable ({e}) — using MemorySaver")
        return None


# Default instance (MemorySaver). agent/api.py upgrades this to a
# Postgres-checkpointed instance at startup when DATABASE_URL is set.
workflow = create_workflow()


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
        "iteration_count":           0,
        "approval_status":           "pending",
        "workflow_complete":         False,
        "work_log":                  [],
        "pydantic_message_history":  history or [],
        "message_history":           [],
    }
