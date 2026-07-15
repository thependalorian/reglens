"use client";

import { useState } from "react";
import type { FindingsReviewPayload, ReviewDecision } from "@/lib/reglens/types";
import { COPY } from "@/lib/reglens/copy";
import { FindingCard } from "./finding-card";
import { CoverageMeter } from "./coverage-meter";

/**
 * The HITL interrupt UI. Surfaces the findings_review interrupt raised by the
 * backend hitl_node with everything the reviewer needs to steer — findings with
 * verbatim citations, grounding, coverage — and the three decisions (approve /
 * reject / refine, with optional exhaustive escalation).
 */
export function FindingsReviewPanel({
  payload,
  onDecision,
}: {
  payload: FindingsReviewPayload;
  onDecision: (decision: ReviewDecision) => void;
}) {
  const [notes, setNotes] = useState("");
  const [exhaustive, setExhaustive] = useState(false);
  const [submitted, setSubmitted] = useState<string | null>(null);

  const decide = (action: ReviewDecision["action"]) => {
    if (action === "refine" && !notes.trim()) return;
    setSubmitted(action);
    onDecision({ action, notes: notes.trim(), exhaustive });
  };

  // The interrupt payload can arrive with an empty/partial shape (e.g. a
  // refine pass that produced no new findings). Never assume the array exists.
  const findings = payload?.findings ?? [];

  if (submitted) {
    return (
      <div className="rounded-card border border-line bg-canvas p-3 text-sm text-ink-muted">
        {COPY.review.submitted}: {submitted}
      </div>
    );
  }

  return (
    <section className="my-2 rounded-card border border-gold-deep/40 bg-gold/[0.08] p-4">
      <h2 className="font-display text-base text-ink">{COPY.review.heading}</h2>
      <p className="mt-1 text-xs text-ink-muted">{COPY.review.subheading}</p>
      {payload.summary ? (
        <p className="mt-2 text-sm text-ink">{payload.summary}</p>
      ) : null}

      <div className="mt-3">
        <CoverageMeter coverage={payload.coverage} />
      </div>

      <div className="mt-3 space-y-3">
        {findings.length === 0 ? (
          <p className="text-sm text-ink-muted">{COPY.review.noFindings}</p>
        ) : (
          findings.map((f) => (
            <FindingCard key={f.finding_id} finding={f} grounding={payload.grounding?.findings?.[f.finding_id]} />
          ))
        )}
      </div>

      <div className="mt-4 space-y-2.5">
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={COPY.review.notesPlaceholder}
          rows={2}
          className="w-full rounded-[4px] border border-line-strong bg-card p-2.5 text-sm text-ink placeholder:text-ink-subtle focus:border-burgundy focus:outline-none"
        />
        <label className="flex items-start gap-2 text-xs text-ink-muted">
          <input
            type="checkbox"
            checked={exhaustive}
            onChange={(e) => setExhaustive(e.target.checked)}
            className="mt-0.5 accent-burgundy"
          />
          <span>
            <span className="font-medium text-ink">{COPY.review.exhaustiveLabel}</span>
            <span className="block text-ink-subtle">{COPY.review.exhaustiveHint}</span>
          </span>
        </label>
        <div className="flex flex-wrap gap-2 pt-1">
          <button
            onClick={() => decide("approve")}
            className="rounded-pill bg-burgundy px-5 py-2 text-sm font-medium text-on-burgundy transition-colors hover:bg-burgundy-deep"
          >
            {COPY.review.approve}
          </button>
          <button
            onClick={() => decide("refine")}
            disabled={!notes.trim()}
            className="rounded-pill border border-line-strong px-5 py-2 text-sm font-medium text-ink transition-colors hover:border-burgundy hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line-strong disabled:hover:text-ink"
          >
            {COPY.review.refine}
          </button>
          <button
            onClick={() => decide("reject")}
            className="rounded-pill px-4 py-2 text-sm font-medium text-ink-muted transition-colors hover:text-burgundy"
          >
            {COPY.review.reject}
          </button>
        </div>
      </div>
    </section>
  );
}
