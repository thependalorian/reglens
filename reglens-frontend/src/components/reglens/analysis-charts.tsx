import type { SludgeFinding } from "@/lib/reglens/types";
import { COPY } from "@/lib/reglens/copy";

/**
 * Derived visualizations of the current findings, computed from shared state
 * (State Rendering — no agent-authored layout, no new fabrication surface).
 * Pure CSS bars: no chart dependency, theme-aware, accessible. Palette stays
 * inside the BoN family (burgundy / gold / olive) so charts never introduce
 * off-brand hues.
 */

interface Segment {
  label: string;
  count: number;
  className: string;
}

function BreakdownBar({ title, segments }: { title: string; segments: Segment[] }) {
  const total = segments.reduce((s, x) => s + x.count, 0);
  if (total === 0) return null;
  const present = segments.filter((s) => s.count > 0);

  return (
    <div>
      <p className="text-xs font-medium text-ink-muted">{title}</p>
      <div
        className="mt-1.5 flex h-2.5 w-full overflow-hidden rounded-full bg-line"
        role="img"
        aria-label={`${title}: ${present.map((s) => `${s.count} ${s.label}`).join(", ")}`}
      >
        {present.map((s) => (
          <div
            key={s.label}
            className={s.className}
            style={{ width: `${(s.count / total) * 100}%` }}
          />
        ))}
      </div>
      <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-ink-muted">
        {present.map((s) => (
          <li key={s.label} className="flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 rounded-[2px] ${s.className}`} />
            {s.label}
            <span className="font-mono tabular-nums text-ink-subtle">{s.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AnalysisCharts({ findings }: { findings: SludgeFinding[] }) {
  if (!findings?.length) return null;

  const count = (pred: (f: SludgeFinding) => boolean) => findings.filter(pred).length;

  const severity: Segment[] = [
    { label: COPY.common.severity.high, count: count((f) => f.severity === "high"), className: "bg-burgundy" },
    { label: COPY.common.severity.medium, count: count((f) => f.severity === "medium"), className: "bg-ochre" },
    { label: COPY.common.severity.low, count: count((f) => f.severity === "low"), className: "bg-ink-subtle" },
  ];

  const types: Segment[] = [
    { label: COPY.charts.types.horizontal, count: count((f) => f.sludge_type === "horizontal"), className: "bg-burgundy" },
    { label: COPY.charts.types.vertical, count: count((f) => f.sludge_type === "vertical"), className: "bg-gold-deep" },
    { label: COPY.charts.types.cumulative, count: count((f) => f.sludge_type === "cumulative"), className: "bg-olive" },
  ];

  return (
    <div className="space-y-4 rounded-card border border-line bg-card p-4">
      <BreakdownBar title={COPY.charts.severity} segments={severity} />
      <BreakdownBar title={COPY.charts.sludgeType} segments={types} />
    </div>
  );
}
