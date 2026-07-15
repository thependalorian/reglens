import type { Coverage } from "@/lib/reglens/types";
import { COPY } from "@/lib/reglens/copy";

/** Honest-coverage disclosure: what fraction of the corpus was examined. */
export function CoverageMeter({ coverage }: { coverage?: Coverage }) {
  if (!coverage || !coverage.corpus_documents) return null;

  const examined = coverage.documents_examined?.length ?? 0;
  const total = coverage.corpus_documents;
  const pct = Math.min(100, Math.round((examined / total) * 100));

  return (
    <div className="rounded-card border border-line bg-card p-3.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-ink">{COPY.coverage.heading}</span>
        <span className="rounded-full bg-canvas px-2 py-0.5 text-ink-muted">
          {COPY.coverage.mode[coverage.mode] ?? coverage.mode}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-line">
        <div className="h-full rounded-full bg-gold-deep" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1.5 text-xs text-ink-muted">
        {COPY.coverage.examined(examined, total)} ({pct}%).{" "}
        <span className="text-ink-subtle">{COPY.coverage.disclaimer}</span>
      </p>
    </div>
  );
}
