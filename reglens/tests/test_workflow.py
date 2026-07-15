import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from workflows.nodes.validate import route_after_validation
from workflows.nodes.hitl     import route_after_hitl


def test_route_after_validation_retry():
    """Invalid + under 3 iterations → retry detect."""
    state = {"validation_result": "invalid", "iteration_count": 1}
    assert route_after_validation(state) == "detect"


def test_route_after_validation_max_iterations():
    """Invalid + 3 iterations → proceed to HITL anyway."""
    state = {"validation_result": "invalid", "iteration_count": 3}
    assert route_after_validation(state) == "hitl"


def test_route_after_validation_valid():
    """Valid → proceed to HITL."""
    state = {"validation_result": "valid", "iteration_count": 1}
    assert route_after_validation(state) == "hitl"


def test_route_after_hitl_approved():
    state = {"approval_status": "approved"}
    assert route_after_hitl(state) == "report"


def test_route_after_hitl_rejected():
    state = {"approval_status": "rejected"}
    assert route_after_hitl(state) == "end"


def test_route_after_hitl_refine():
    """Reviewer refine loops back through retrieval with feedback."""
    state = {"approval_status": "refine"}
    assert route_after_hitl(state) == "retrieve"


def test_route_after_hitl_pending_defensive():
    """Pending never reaches routing (interrupt pauses first); defensively ends."""
    state = {"approval_status": "pending"}
    assert route_after_hitl(state) == "end"


def test_initial_state_structure():
    from workflows.graph import create_initial_state
    state = create_initial_state("test query", "uid~sess1", "req1", "uid")
    assert state["query"]           == "test query"
    assert state["iteration_count"] == 0
    assert state["approval_status"] == "pending"
    assert state["work_log"]        == []