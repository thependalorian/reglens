from __future__ import annotations
import json
import uuid as _uuid
from typing import Optional, Callable
from ..state import SludgeWorkflowState
from agent.agent import report_generator
from agent.tools import AgentDeps
from agent.clients import get_pg_pool, get_embedding_client
from agent.db_utils import (
    save_finding,
    update_finding_status,
    update_session_status,
    write_audit_log,
)


async def report_node(
    state:  SludgeWorkflowState,
    config: Optional[dict] = None,
    writer: Optional[Callable] = None,
) -> dict:
    if writer:
        writer("\n**[5/5] Generating remediation report...**\n\n")

    pool        = await get_pg_pool()
    # AG-UI runs carry no session_id in state — fall back to the
    # LangGraph thread id (a UUID from CopilotKit) for persistence keys.
    session_uid = state.get("session_id", "") or (
        (config or {}).get("configurable", {}).get("thread_id", "")
    )
    reviewer_uid = state.get("reviewer_uid", "system")

    # Persistence keys are UUID columns. Real runs key on a UUID thread id;
    # if the id is malformed (never in normal use), skip DB persistence and
    # still generate the report rather than 500-ing the whole stream.
    def _is_uuid(s: str) -> bool:
        try:
            _uuid.UUID(str(s))
            return True
        except (ValueError, AttributeError, TypeError):
            return False

    persist = _is_uuid(session_uid)

    try:
        # 1. Persist findings (UUIDs from app, link rows inserted, no triggers)
        finding_uids = []
        if persist:
            for fd in state.get("sludge_findings", []):
                fuid = await save_finding(pool, session_uid, fd)
                await update_finding_status(
                    pool,
                    finding_uid=fuid,
                    status="approved",
                    user_uid=reviewer_uid,
                    session_id=session_uid,
                    notes=state.get("reviewer_notes", "Approved via HITL"),
                )
                finding_uids.append(fuid)

        # 2. Build adaptive report prompt from corpus_map
        deps = AgentDeps(
            pool=             pool,
            embedding_client= get_embedding_client(),
            corpus_map=       state.get("corpus_map", {}),
        )

        coverage = state.get("coverage", {})
        report_input = (
            f"Generate the remediation report.\n\n"
            f"COVERAGE DATA (for the mandatory Scope & Coverage section):\n"
            f"{json.dumps(coverage, indent=2)}\n\n"
            f"Validated findings ({len(finding_uids)} total) — their citations "
            f"populate the mandatory References section:\n"
            f"{json.dumps(state.get('sludge_findings', []), indent=2)}\n\n"
            f"Citation grounding results:\n"
            f"{json.dumps(state.get('grounding', {}), indent=2)}\n\n"
            f"Reviewer notes: {state.get('reviewer_notes', 'None')}\n"
            f"Validation iterations: {state.get('iteration_count', 0)}\n"
            f"Audit trail:\n{chr(10).join(state.get('work_log', []))}"
        )

        # 3. Stream the report
        full_report = ""
        async with report_generator.iter(report_input, deps=deps) as run:
            async for node in run:
                if report_generator.is_model_request_node(node):
                    async with node.stream(run.ctx) as stream:
                        from pydantic_ai.messages import PartDeltaEvent, TextPartDelta
                        async for event in stream:
                            if isinstance(event, PartDeltaEvent) and isinstance(
                                event.delta, TextPartDelta
                            ):
                                delta = event.delta.content_delta
                                if delta:
                                    if writer:
                                        writer(delta)
                                    full_report += delta

        # 4. Update session status — application, not trigger
        if persist:
            await update_session_status(pool, session_uid, "complete", "approved")
            await write_audit_log(
                pool,
                session_id=session_uid,
                description=f"Report generated. {len(finding_uids)} findings persisted.",
                log_type="report",
                status_from="hitl_approved",
                status_to="complete",
                iteration_count=state.get("iteration_count", 0),
            )

        from langchain_core.messages import AIMessage
        return {
            "final_report":    full_report,
            "messages":        [AIMessage(content=full_report)],
            "workflow_complete": True,
            "status":          "complete",
            "work_log": [
                f"[report] {len(finding_uids)} findings saved | report generated"
            ],
        }

    except Exception as e:
        if persist:
            try:
                await write_audit_log(pool, session_uid, f"Report error: {e}", "error")
            except Exception:
                pass  # never let audit logging mask the real error
        return {
            "status":        "error",
            "error_message": str(e),
            "work_log":      [f"[report] ERROR: {e}"],
        }