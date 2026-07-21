from __future__ import annotations
from typing import Optional, Callable

from langgraph.types import interrupt

from ..state import SludgeWorkflowState


async def hitl_node(
    state:  SludgeWorkflowState,
    writer: Optional[Callable] = None,
) -> dict:
    """
    Human-in-the-loop gate — dynamic LangGraph interrupt.

    The graph pauses here (checkpointed) until a reviewer resumes with
    Command(resume={"action": "approve|reject|refine",
                    "notes": str, "exhaustive": bool}).
    Both clients use the same mechanism: the CLI via POST /api/reglens/approve
    and the web UI via the CopilotKit/AG-UI interrupt flow.
    """
    findings   = state.get("sludge_findings", [])
    high_count = sum(1 for f in findings if f.get("severity") == "high")
    corpus_map = state.get("corpus_map", {})

    validation_result = state.get("validation_result", "")
    validation_issues = state.get("validation_issues", [])
    auto_validated = validation_result == "valid"

    if writer:
        warning = ""
        if not auto_validated:
            warning = (
                f"\n**WARNING: these findings did NOT pass automated validation** "
                f"after {state.get('iteration_count', 0)} attempts — "
                f"{'; '.join(str(i) for i in validation_issues[:2]) or 'see audit trail'}\n"
            )
        writer(
            f"\n**[HITL] Expert Review Required**\n"
            f"Corpus: {corpus_map.get('coverage_summary', 'regulatory documents')}\n"
            f"Findings: {len(findings)} total | {high_count} high severity\n"
            f"Validation iterations: {state.get('iteration_count', 0)}\n"
            f"{warning}\n"
            f"Options: approve (publish) | reject (discard) | "
            f"refine (send feedback back for another pass, optionally exhaustive)\n"
        )

    # Findings reach HITL two ways: validation passed, or the 3-iteration
    # budget was exhausted while it kept failing (route_after_validation sends
    # to hitl either way — a human decides rather than the pipeline silently
    # looping forever or auto-publishing). Surface which one happened: a
    # reviewer approving a NEVER-validated finding should know that up front,
    # not discover it by reading the audit trail.
    # Pauses execution; the payload is what review UIs render.
    decision = interrupt({
        "type":      "findings_review",
        "summary":   state.get("detection_summary", ""),
        "findings":  findings,
        "coverage":  state.get("coverage", {}),
        "grounding": state.get("grounding", {}),
        "iteration_count": state.get("iteration_count", 0),
        "auto_validated":    auto_validated,
        "validation_issues": validation_issues if not auto_validated else [],
    })

    # CopilotKit's resolve() may deliver the decision as a JSON string
    if isinstance(decision, str):
        import json
        try:
            decision = json.loads(decision)
        except (ValueError, TypeError):
            decision = {"action": decision}
    decision = decision if isinstance(decision, dict) else {"action": str(decision)}
    action     = decision.get("action", "reject")
    notes      = decision.get("notes", "") or ""
    exhaustive = bool(decision.get("exhaustive", False))

    status_map = {"approve": "approved", "reject": "rejected", "refine": "refine"}
    approval_status = status_map.get(action, "rejected")

    update: dict = {
        "approval_status": approval_status,
        "reviewer_notes":  notes,
        "status":          f"review_{approval_status}",
        "work_log": [
            f"[hitl] decision={action}"
            f"{' exhaustive' if action == 'refine' and exhaustive else ''} | "
            f"findings={len(findings)} high={high_count}"
        ],
    }
    if approval_status == "refine":
        # Reviewer feedback drives the next detection pass; reset the
        # validator iteration budget for the new cycle.
        update["validation_feedback"] = (
            f"EXPERT REVIEWER FEEDBACK (address directly): {notes or 'Dig deeper.'}"
        )
        update["iteration_count"] = 0
        update["exhaustive"]      = exhaustive

    return update


def route_after_hitl(state: SludgeWorkflowState) -> str:
    status = state.get("approval_status", "pending")
    if status == "approved":
        return "report"
    if status == "refine":
        # Reviewer sent the analysis back: re-retrieve (exhaustive if the
        # reviewer escalated) and re-detect with their feedback injected.
        return "retrieve"
    if status == "rejected":
        return "end"
    return "end"
