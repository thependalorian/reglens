from __future__ import annotations
from typing import Annotated, List, Optional, TypedDict
from operator import add
from langgraph.graph.message import add_messages
from pydantic_ai.messages import ModelMessage


class SludgeWorkflowState(TypedDict, total=False):
    # Chat transcript (AG-UI/CopilotKit clients deliver the user query
    # here and read assistant replies from here; the CLI uses `query`)
    messages:       Annotated[list, add_messages]

    # Input
    query:          str
    session_id:     str
    request_id:     str
    user_uid:       str
    exhaustive:     bool               # full-corpus sweep instead of top-k retrieval

    # Triage (intent gate — populated by triage_node)
    intent:         str                # analysis | casual | off_topic | unanswerable

    # Corpus discovery (adaptive — populated by discover_node)
    corpus_map:     dict

    # RAG
    retrieved_chunks: List[dict]

    # Coverage disclosure (populated by detect_node)
    coverage:       dict               # documents_examined, chunks_examined, corpus totals

    # Citation grounding (mechanical verification results)
    grounding:      dict

    # Detection
    sludge_findings:    List[dict]
    detection_summary:  str
    iteration_count:    int

    # Validation (guardrail loop)
    validation_result:   str           # "valid" | "invalid"
    validation_feedback: str
    validation_issues:   List[str]

    # HITL
    approval_status:  str              # "pending" | "approved" | "rejected"
    reviewer_notes:   str
    reviewer_uid:     str

    # Report
    final_report: str

    # Control
    status:            str
    error_message:     str
    workflow_complete: bool

    # Append-only audit trail (Wiebe: log pattern)
    work_log: Annotated[List[str], add]

    # Pydantic AI message history
    pydantic_message_history: List[ModelMessage]
    message_history:          List[bytes]