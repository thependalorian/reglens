/** Mirrors agent/models.py and workflows/state.py on the Python backend. */

export interface Citation {
  document_title: string;
  source_reference: string;
  verbatim_quote: string;
  chunk_uid: string;
}

export interface SludgeFinding {
  finding_id: string;
  sludge_type: "horizontal" | "vertical" | "cumulative";
  title: string;
  description: string;
  source_provisions: Citation[];
  overlapping_provisions: Citation[];
  affected_domains: string[];
  severity: "high" | "medium" | "low";
  recommended_action: string;
  rationale: string;
  estimated_burden: string;
  cross_cutting: boolean;
  confidence_score: number;
}

export interface Coverage {
  documents_examined: string[];
  chunks_examined: number;
  corpus_documents: number;
  corpus_chunks: number;
  mode: "retrieval" | "exhaustive";
}

export interface Grounding {
  findings: Record<
    string,
    { verified: number; unverified: number; unverified_quotes: string[] }
  >;
  total_verified: number;
  total_unverified: number;
}

/** Subset of SludgeWorkflowState the UI reads via useAgent().state. */
export interface ReglensAgentState {
  query?: string;
  intent?: string;
  status?: string;
  corpus_map?: CorpusMap;
  sludge_findings?: SludgeFinding[];
  detection_summary?: string;
  coverage?: Coverage;
  grounding?: Grounding;
  iteration_count?: number;
  approval_status?: string;
  final_report?: string;
  work_log?: string[];
  exhaustive?: boolean;
}

/** Payload of the findings_review interrupt raised by hitl_node. */
export interface FindingsReviewPayload {
  type: "findings_review";
  summary: string;
  findings: SludgeFinding[];
  coverage: Coverage;
  grounding: Grounding;
  iteration_count: number;
  /** false when findings reached review by exhausting the validation retry
   *  budget rather than passing automated validation — the reviewer is the
   *  first check these findings have actually had. */
  auto_validated?: boolean;
  validation_issues?: string[];
}

export interface ReviewDecision {
  action: "approve" | "reject" | "refine";
  notes: string;
  exhaustive: boolean;
}

export interface CorpusMap {
  document_count: number;
  corpus_chunk_count: number;
  document_titles: string[];
  regulatory_bodies: string[];
  domains: string[];
  document_types: string[];
  regulatory_levels: string[];
  coverage_summary: string;
}

/** Row from GET /api/reglens/documents — the ingest pipeline view. */
export interface DocumentRow {
  document_uid: string;
  title: string;
  regulatory_body: string;
  domain: string;
  document_type: string;
  status: "active" | "processing" | "failed";
  chunk_count: number;
  file_name: string;
  error?: string | null;
  ingested_at: string | null;
}

export interface FrameworkGap {
  gap_id: string;
  description: string;
  divergence_type: string;
  harmonisation_recommendation: string;
  priority: "high" | "medium" | "low";
}

export interface CrossBorderAnalysis {
  label_a: string;
  label_b: string;
  topic: string;
  gaps: FrameworkGap[];
  total_gaps: number;
  harmonisation_score: number;
  key_friction_points: string[];
  coordination_recommendations: string[];
  executive_summary: string;
}

export interface PrecheckResult {
  findings: SludgeFinding[];
  summary: string;
  total_conflicts: number;
  high_priority: number;
  confidence_score: number;
}
