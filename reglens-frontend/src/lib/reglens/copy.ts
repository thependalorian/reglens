/** All user-facing copy (workspace rule: no hardcoded strings on pages). No emojis. */
export const COPY = {
  appName: "RegLens",
  tagline: "Regulatory sludge intelligence for supervisors",

  tabs: {
    analysis: "Analysis",
    documents: "Documents",
  },

  chat: {
    title: "Regulatory Analysis",
    placeholder: "Ask about overlaps, conflicts, or gaps in the ingested corpus...",
    initial:
      "I analyze the ingested regulatory corpus for overlapping, conflicting, and outdated obligations. Every finding carries verbatim, mechanically verified citations, and nothing is published without your review.",
  },

  stepper: {
    heading: "Agent activity",
    steps: {
      triage: "Triage",
      discover: "Corpus discovery",
      retrieve: "Retrieval",
      detect: "Detection",
      validate: "Citation validation",
      review: "Expert review",
      report: "Report",
    },
    idle: "Ask a question to begin an analysis.",
  },

  review: {
    heading: "Expert review required",
    subheading:
      "These findings carry mechanically verified citations. Approve to publish, reject to discard, or send feedback back to the analyst.",
    confidence: "Evidence-based confidence",
    sources: "Source provisions",
    overlaps: "Overlapping provisions",
    grounding: (v: number, t: number) => `${v}/${t} citations verified`,
    approve: "Approve and publish",
    reject: "Reject",
    refine: "Refine",
    exhaustiveLabel: "Escalate to exhaustive full-corpus sweep",
    exhaustiveHint:
      "Reads every document in the corpus (one digest per document). Slower, complete coverage.",
    notesPlaceholder: "Reviewer notes (required for refine)...",
    submitted: "Decision submitted",
    noFindings: "No findings were surfaced for this pass. Refine to search further, or reject to end.",
  },

  coverage: {
    heading: "Coverage",
    examined: (x: number, n: number) => `${x} of ${n} documents examined`,
    mode: { retrieval: "Targeted retrieval", exhaustive: "Exhaustive sweep" },
    disclaimer: "Findings are limited to examined material.",
  },

  charts: {
    severity: "Findings by severity",
    sludgeType: "Findings by sludge type",
    types: {
      horizontal: "Horizontal",
      vertical: "Vertical",
      cumulative: "Cumulative",
    },
  },

  report: {
    heading: "Remediation report",
    empty: "The approved report will appear here.",
  },

  documents: {
    heading: "Ingest pipeline",
    subheading:
      "Manage the documents RegLens analyzes. Uploads are parsed, embedded, and added to the corpus in the background.",
    upload: "Upload document",
    uploadHint: "PDF, DOCX, TXT, or MD",
    uploading: "Uploading...",
    empty: "No documents ingested yet. Upload one to begin.",
    colTitle: "Document",
    colBody: "Body",
    colDomain: "Domain",
    colChunks: "Chunks",
    colStatus: "Status",
    remove: "Remove",
    confirmRemove: "Remove this document and all its chunks from the corpus?",
    status: { active: "Active", processing: "Processing", failed: "Failed" },
    totals: (docs: number, chunks: number) => `${docs} documents, ${chunks} chunks`,
    skipped: "Already ingested (identical file).",
    error: "Could not reach the backend. Is the API running?",
  },

  common: {
    severity: { high: "High", medium: "Medium", low: "Low" },
    error: "Something went wrong. Check the backend logs and try again.",
  },
} as const;
