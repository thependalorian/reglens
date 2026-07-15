import type { Citation, SludgeFinding } from "@/lib/reglens/types";
import { COPY } from "@/lib/reglens/copy";

/** Render the machine locator ("section=9.1 | chunk#4 | page=3") as a clean,
 *  human label ("Section 9.1 · p.3 · chunk 4"). Leaves free-text locators
 *  (e.g. "Section 4.2") untouched. */
function formatLocator(ref: string): string {
  if (!ref) return "";
  if (!/[=#]/.test(ref)) return ref;
  const out: string[] = [];
  for (const part of ref.split("|").map((p) => p.trim())) {
    const section = part.match(/^section=(.+)$/i);
    const page = part.match(/^page=(.+)$/i);
    const chunk = part.match(/^chunk#?=?(.+)$/i);
    if (section) out.push(`Section ${section[1]}`);
    else if (page) out.push(`p.${page[1]}`);
    else if (chunk) out.push(`chunk ${chunk[1]}`);
    else if (part) out.push(part);
  }
  return out.join(" · ");
}

const SEVERITY: Record<string, string> = {
  high: "bg-burgundy/10 text-burgundy border-burgundy/25",
  medium: "bg-ochre/10 text-ochre border-ochre/30",
  low: "bg-ink-muted/10 text-ink-muted border-line",
};

function CitationList({ label, citations }: { label: string; citations: Citation[] }) {
  if (!citations?.length) return null;
  return (
    <div className="mt-3">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
      <ul className="mt-1.5 space-y-2">
        {citations.map((c, i) => (
          <li key={i} className="rounded-[4px] border border-line bg-canvas p-2.5">
            <p className="text-xs font-medium text-ink">
              {c.document_title}
              {c.source_reference ? ` — ${formatLocator(c.source_reference)}` : ""}
            </p>
            <blockquote className="mt-1 border-l-2 border-gold pl-2.5 text-xs italic text-ink-muted">
              {c.verbatim_quote}
            </blockquote>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function FindingCard({
  finding,
  grounding,
}: {
  finding: SludgeFinding;
  grounding?: { verified: number; unverified: number };
}) {
  const sev = SEVERITY[finding.severity] ?? SEVERITY.low;
  const confidencePct = Math.round((finding.confidence_score ?? 0) * 100);
  const total = grounding ? grounding.verified + grounding.unverified : 0;
  const confidenceColor =
    confidencePct >= 85 ? "bg-olive" : confidencePct >= 45 ? "bg-gold-deep" : "bg-burgundy";

  return (
    <article className="rounded-card border border-line bg-card p-4">
      <header className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-ink-subtle">{finding.finding_id}</span>
        <h3 className="text-sm font-semibold text-ink">{finding.title}</h3>
        <span className={`ml-auto rounded-[4px] border px-2 py-0.5 text-xs font-medium ${sev}`}>
          {COPY.common.severity[finding.severity] ?? finding.severity}
        </span>
        <span className="rounded-[4px] border border-line bg-canvas px-2 py-0.5 text-xs text-ink-muted">
          {finding.sludge_type}
        </span>
      </header>

      <p className="mt-2.5 text-sm leading-relaxed text-ink">{finding.description}</p>
      <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">{finding.rationale}</p>

      <div className="mt-3.5">
        <div className="flex items-center justify-between text-xs text-ink-muted">
          <span>{COPY.review.confidence}</span>
          <span className="font-mono tabular-nums">
            {confidencePct}%
            {grounding && total > 0 ? ` — ${COPY.review.grounding(grounding.verified, total)}` : ""}
          </span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-line">
          <div
            className={`h-full rounded-full ${confidenceColor}`}
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>

      <CitationList label={COPY.review.sources} citations={finding.source_provisions} />
      <CitationList label={COPY.review.overlaps} citations={finding.overlapping_provisions} />
    </article>
  );
}
