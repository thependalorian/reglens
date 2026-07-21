from __future__ import annotations
from typing import Annotated, List, Optional, TypedDict
from operator import add
from pydantic_ai.messages import ModelMessage

# ag_ui_langgraph requires LangChain-format messages for time-travel
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class SludgeWorkflowState(TypedDict, total=False):
    # Input
    query:          str
    session_id:     str
    request_id:     str
    user_uid:       str
    exhaustive:     bool   # full-corpus sweep vs top-k retrieval

    # ag_ui_langgraph time-travel support
    # This field MUST be present and use add_messages reducer.
    # ag_ui_langgraph tracks message IDs through this list.
    # Without it: ValueError: Message ID not found in history
    messages: Annotated[List[BaseMessage], add_messages]

    # Corpus (auto-discovered)
    corpus_map:     dict

    # RAG
    retrieved_chunks: List[dict]

    # Detection
    sludge_findings:    List[dict]
    detection_summary:  str
    iteration_count:    int

    # Validation
    validation_result:   str
    validation_feedback: str
    validation_issues:   List[str]

    # HITL
    approval_status:  str
    reviewer_notes:   str
    reviewer_uid:     str

    # Report
    final_report: str

    # Control
    status:            str
    error_message:     str
    workflow_complete: bool

    # Append-only audit trail
    work_log: Annotated[List[str], add]

    # Pydantic AI message history (separate from LangChain messages above)
    pydantic_message_history: List[ModelMessage]
    message_history:          List[bytes]
