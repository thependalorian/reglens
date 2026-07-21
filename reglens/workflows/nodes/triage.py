"""
Triage node — intent gate before any retrieval or analysis.
Anthropic routing pattern: classify the input with a mini model and
short-circuit casual chat, off-topic requests, and unanswerable asks
so they never trigger the full analysis workflow.
Cost: one mini-model call. Failure mode: defaults to analysis (fail-open).
"""
from __future__ import annotations
from typing import Optional, Callable

from pydantic_ai import Agent

from agent.providers import get_llm_model
from agent.models import TriageDecision
from agent.prompts import TRIAGE_PROMPT
from ..state import SludgeWorkflowState


triage_agent = Agent(
    get_llm_model(use_capable=False),
    output_type=TriageDecision,
    system_prompt=TRIAGE_PROMPT,
)


def _query_from_state(state: SludgeWorkflowState) -> str:
    """CLI sets `query` directly; AG-UI clients deliver it as the last
    human message in `messages`."""
    query = state.get("query", "")
    if query:
        return query
    for m in reversed(state.get("messages") or []):
        role = getattr(m, "type", None) or (
            m.get("role") if isinstance(m, dict) else None
        )
        if role in ("human", "user"):
            content = getattr(m, "content", None) or (
                m.get("content") if isinstance(m, dict) else ""
            )
            return content if isinstance(content, str) else str(content)
    return ""


async def triage_node(
    state:  SludgeWorkflowState,
    writer: Optional[Callable] = None,
) -> dict:
    query = _query_from_state(state)

    try:
        result   = await triage_agent.run(query)
        decision = result.output
    except Exception as e:
        # Fail open: a broken triage must never block real analysis
        return {
            "intent":   "analysis",
            "status":   "triaged",
            "work_log": [f"[triage] ERROR (fail-open to analysis): {e}"],
        }

    if decision.intent != "analysis":
        reply = decision.reply or (
            "This request is outside the scope of RegLens. RegLens analyzes "
            "ingested regulatory documents for overlaps, conflicts, and gaps."
        )
        if writer:
            writer(f"\n{reply}\n")
        from langchain_core.messages import AIMessage
        return {
            "intent":            decision.intent,
            "final_report":      reply,
            "messages":          [AIMessage(content=reply)],
            "workflow_complete": True,
            "status":            "triaged_out",
            "work_log":          [f"[triage] intent={decision.intent} — short-circuited"],
        }

    return {
        "intent":   "analysis",
        "query":    query,
        "status":   "triaged",
        "work_log": [f"[triage] intent=analysis | q='{query[:50]}'"],
    }


def route_after_triage(state: SludgeWorkflowState) -> str:
    return "discover" if state.get("intent", "analysis") == "analysis" else "end"
