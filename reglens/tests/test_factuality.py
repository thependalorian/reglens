"""
Factuality guardrail tests:
- mechanical citation verification (ground truth from the environment)
- evidence-based confidence scoring
- source independence (horizontal findings must span >=2 documents)
- triage routing (intent gate keeps casual chat out of the workflow)
"""
from agent.tools import (
    verify_citations_mechanically,
    grounded_confidence,
    check_source_independence,
)
from workflows.nodes.triage import route_after_triage


CHUNKS = [
    {"chunk_uid": "c1", "document_uid": "docA", "content": (
        "Section 4.1: Every payment service provider shall verify the "
        "identity of a customer before establishing a business relationship."
    )},
    {"chunk_uid": "c2", "document_uid": "docA", "content": (
        "Section 5.1: Providers shall submit a monthly transaction report "
        "to the Bank within 15 business days of month end."
    )},
    {"chunk_uid": "c3", "document_uid": "docB", "content": (
        "Section 2.1: Reporting entities must file a separate quarterly "
        "disclosure with the Authority covering the same transactions."
    )},
]


def _finding(fid: str, quotes: list) -> dict:
    return {
        "finding_id": fid,
        "confidence_score": 0.9,
        "source_provisions": [
            {"document_title": "Test", "source_reference": "S",
             "verbatim_quote": q, "chunk_uid": "c1"} for q in quotes
        ],
        "overlapping_provisions": [],
    }


def test_verified_quote_passes():
    findings = [_finding("F001", [
        "shall verify the identity of a customer before establishing"
    ])]
    g = verify_citations_mechanically(findings, CHUNKS)
    assert g["total_verified"] == 1
    assert g["total_unverified"] == 0


def test_whitespace_and_case_tolerated():
    findings = [_finding("F001", [
        "SHALL   verify the\nidentity of a customer"
    ])]
    g = verify_citations_mechanically(findings, CHUNKS)
    assert g["total_verified"] == 1


def test_fabricated_quote_fails():
    findings = [_finding("F001", [
        "providers must report all transactions weekly to NAMFISA"
    ])]
    g = verify_citations_mechanically(findings, CHUNKS)
    assert g["total_unverified"] == 1
    assert g["findings"]["F001"]["unverified"] == 1


def test_grounded_confidence_from_evidence():
    findings = [_finding("F001", [
        "shall verify the identity of a customer",       # real
        "totally invented obligation text",              # fabricated
    ])]
    g = verify_citations_mechanically(findings, CHUNKS)
    score = grounded_confidence(findings[0], g)
    assert score == 0.5     # 1 of 2 verified, below the 0.9 self-report


def test_zero_citations_means_zero_confidence():
    finding = {"finding_id": "F002", "confidence_score": 0.95,
               "source_provisions": [], "overlapping_provisions": []}
    g = verify_citations_mechanically([finding], CHUNKS)
    assert grounded_confidence(finding, g) == 0.0


def test_self_report_caps_confidence():
    findings = [_finding("F001", ["shall verify the identity of a customer"])]
    findings[0]["confidence_score"] = 0.3   # model itself is unsure
    g = verify_citations_mechanically(findings, CHUNKS)
    assert grounded_confidence(findings[0], g) == 0.3


def _horizontal_finding(fid: str, source_chunk_uid: str, overlap_chunk_uid: str) -> dict:
    return {
        "finding_id": fid,
        "sludge_type": "horizontal",
        "title": "Test overlap",
        "source_provisions": [
            {"document_title": "A", "source_reference": "S",
             "verbatim_quote": "x", "chunk_uid": source_chunk_uid},
        ],
        "overlapping_provisions": [
            {"document_title": "B", "source_reference": "S",
             "verbatim_quote": "y", "chunk_uid": overlap_chunk_uid},
        ],
    }


def test_horizontal_finding_same_document_fails_independence():
    # The exact failure mode caught live: both citations trace to docA.
    findings = [_horizontal_finding("F001", "c1", "c2")]
    result = check_source_independence(findings, CHUNKS)
    assert result["F001"]["distinct_documents"] == 1
    assert result["F001"]["independent"] is False


def test_horizontal_finding_two_documents_passes_independence():
    findings = [_horizontal_finding("F001", "c1", "c3")]
    result = check_source_independence(findings, CHUNKS)
    assert result["F001"]["distinct_documents"] == 2
    assert result["F001"]["independent"] is True


def test_vertical_finding_not_subject_to_independence_check():
    finding = _horizontal_finding("F001", "c1", "c2")
    finding["sludge_type"] = "vertical"
    result = check_source_independence([finding], CHUNKS)
    assert "F001" not in result


def test_independence_ignores_citations_with_no_matching_chunk():
    # A fabricated/unresolvable chunk_uid must not count toward independence
    # (mechanical verification catches fabrication separately; this check
    # only counts documents that are actually in the retrieved evidence).
    findings = [_horizontal_finding("F001", "c1", "nonexistent-chunk")]
    result = check_source_independence(findings, CHUNKS)
    assert result["F001"]["distinct_documents"] == 1
    assert result["F001"]["independent"] is False


def test_triage_routes_analysis_to_discover():
    assert route_after_triage({"intent": "analysis"}) == "discover"


def test_triage_short_circuits_casual():
    assert route_after_triage({"intent": "casual"}) == "end"
    assert route_after_triage({"intent": "off_topic"}) == "end"
    assert route_after_triage({"intent": "unanswerable"}) == "end"
    # Ambiguous regulatory requests get a clarifying question, not a guess
    assert route_after_triage({"intent": "clarification_needed"}) == "end"


def test_triage_defaults_to_analysis():
    assert route_after_triage({}) == "discover"
