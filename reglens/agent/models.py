from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class SludgeType(str, Enum):
    HORIZONTAL = "horizontal"   # overlapping rules across parallel bodies/frameworks
    VERTICAL   = "vertical"     # accumulation down the stack statute→reg→guidance
    CUMULATIVE = "cumulative"   # barnacle build-up over time


class Severity(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class RemediationAction(str, Enum):
    DELETE       = "delete"
    CONSOLIDATE  = "consolidate"
    CLARIFY      = "clarify"
    ESCALATE     = "escalate"   # requires cross-agency coordination


class Citation(BaseModel):
    """
    A grounded citation pinned to a retrieved corpus chunk.
    verbatim_quote MUST be copied exactly from a retrieved chunk —
    it is mechanically verified against the corpus before publication.
    """
    document_title:   str = Field(..., description="Title of the source document as shown in [SOURCE ...] header")
    source_reference: str = Field(default="", description="Provision locator copied from the [SOURCE ...] header (section=/page=/chunk#), e.g. 'section=9.1 | chunk#4'")
    verbatim_quote:   str = Field(..., max_length=800, description="Exact text copied from the retrieved chunk — quote the full operative provision, not a fragment")
    chunk_uid:        str = Field(default="", description="chunk_uid copied from the [SOURCE ...] header")


class SludgeFinding(BaseModel):
    finding_id:             str   = Field(..., description="Sequential ID e.g. F001")
    sludge_type:            SludgeType
    title:                  str
    description:            str
    source_provisions:      List[Citation] = Field(..., description="Grounded citations from corpus")
    overlapping_provisions: List[Citation] = Field(..., description="Citations that duplicate/conflict")
    affected_domains:       List[str] = Field(default_factory=list, description="Discovered from corpus")
    severity:               Severity
    recommended_action:     RemediationAction
    rationale:              str   = Field(..., description="Why this is sludge not intentional ambiguity")
    estimated_burden:       str   = Field(default="", description="Compliance cost if estimable")
    cross_cutting:          bool  = Field(default=False, description="Affects multiple domains/bodies")


class SludgeAnalysis(BaseModel):
    findings:                    List[SludgeFinding]
    total_findings:              int
    high_severity_count:         int
    summary:                     str
    confidence_score:            float = Field(ge=0.0, le=1.0)
    primary_sludge_vector:       SludgeType
    domains_analyzed:            List[str] = Field(default_factory=list)
    regulatory_bodies_identified: List[str] = Field(default_factory=list)


class CitationValidation(BaseModel):
    is_valid:             bool
    unverified_citations: List[str]          = Field(default_factory=list)
    issues:               List[str]          = Field(default_factory=list)
    corrected_findings:   Optional[List[SludgeFinding]] = None


class CorpusMap(BaseModel):
    """
    Built dynamically from ingested document metadata.
    Never hardcoded — always reflects what is actually in the corpus.
    """
    document_count:      int
    regulatory_bodies:   List[str]
    domains:             List[str]
    document_types:      List[str]
    regulatory_levels:   List[str]
    coverage_summary:    str


class SludgeRequest(BaseModel):
    """
    No jurisdiction or domain fields — system discovers these from corpus.
    exhaustive=True sweeps every corpus document (map-reduce) instead of
    top-k retrieval — complete coverage, higher cost.
    """
    query:      str
    session_id: str
    request_id: Optional[str] = None
    exhaustive: bool = False


class TriageDecision(BaseModel):
    """
    Intent gate output — routes casual chat, noise, and ambiguous
    requests away from the full analysis workflow (routing pattern).
    """
    intent: str = Field(
        ...,
        description="analysis | clarification_needed | casual | off_topic | unanswerable",
    )
    analysis_type: Optional[str] = Field(
        default=None,
        description="sludge_detection | precheck | cross_border | general (analysis intent only)",
    )
    reply: str = Field(
        default="",
        description="Short direct reply, or the single clarifying question",
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ApprovalRequest(BaseModel):
    """
    HITL decision. action:
      approve — publish findings, generate report
      reject  — end the workflow, nothing published
      refine  — send reviewer_notes back to the detector for another
                pass; set exhaustive=True to escalate to a full-corpus
                sweep when retrieval-based findings were unsatisfying
    `approved` retained for backward compatibility (True=approve,
    False=reject) when `action` is not supplied.
    """
    session_id:      str
    approved:        bool = False
    action:          Optional[str] = None   # approve | reject | refine
    reviewer_notes:  Optional[str] = ""
    exhaustive:      bool = False


class DraftCheckRequest(BaseModel):
    """
    Pre-rulemaking check: compare a draft regulatory text
    against the existing ingested corpus.
    """
    draft_title:  str
    draft_text:   str
    session_id:   str
    request_id:   Optional[str] = None


class CompareRequest(BaseModel):
    """
    Cross-border comparison: compare two sets of documents
    identified by metadata filters.
    Returns a gap analysis and harmonisation score.
    """
    label_a:        str = Field(..., description="e.g. 'UK AML Framework'")
    label_b:        str = Field(..., description="e.g. 'Singapore MAS AML'")
    filter_a:       Dict[str, Any] = Field(..., description="Metadata filter for corpus A")
    filter_b:       Dict[str, Any] = Field(..., description="Metadata filter for corpus B")
    topic:          str = Field(..., description="Topic to compare e.g. 'AML/CFT reporting'")
    session_id:     str
    request_id:     Optional[str] = None


class FrameworkGap(BaseModel):
    gap_id:             str
    description:        str
    present_in_a:       bool
    present_in_b:       bool
    provision_a:        str = ""
    provision_b:        str = ""
    divergence_type:    str = Field(
        ..., description="missing | threshold_difference | terminology | procedural | scope"
    )
    harmonisation_recommendation: str
    priority:           str = Field(..., description="high | medium | low")


class CrossBorderAnalysis(BaseModel):
    label_a:                    str
    label_b:                    str
    topic:                      str
    gaps:                       List[FrameworkGap]
    total_gaps:                 int
    harmonisation_score:        float = Field(
        ge=0.0, le=1.0,
        description="0 = completely divergent, 1 = fully harmonised"
    )
    key_friction_points:        List[str]
    coordination_recommendations: List[str]
    executive_summary:          str