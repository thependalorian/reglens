import { COPY } from "@/lib/reglens/copy";
import type { ReglensAgentState } from "@/lib/reglens/types";

const STEPS = [
  { id: "triage", label: COPY.stepper.steps.triage },
  { id: "discover", label: COPY.stepper.steps.discover },
  { id: "retrieve", label: COPY.stepper.steps.retrieve },
  { id: "detect", label: COPY.stepper.steps.detect },
  { id: "validate", label: COPY.stepper.steps.validate },
  { id: "review", label: COPY.stepper.steps.review },
  { id: "report", label: COPY.stepper.steps.report },
] as const;

function doneIndex(status: string | undefined): number {
  if (!status) return -1;
  const order: Record<string, number> = {
    triaged: 0,
    triaged_out: 0, // casual/off-topic: only triage ran, no analysis steps
    discovered: 1,
    retrieved: 2,
    detected: 3,
    validation_failed: 3,
    validated: 4,
    awaiting_review: 4,
    review_approved: 5,
    review_refine: 2,
    review_rejected: 6,
    complete: 6,
    fallback_complete: 6,
  };
  return order[status] ?? -1;
}

export function WorkflowStepper({
  state,
  running,
}: {
  state: ReglensAgentState;
  running: boolean;
}) {
  const done = doneIndex(state.status);
  const reviewing = state.status === "awaiting_review";
  const activeIdx = reviewing ? 5 : running ? done + 1 : -1;
  const workLog = state.work_log ?? [];

  return (
    <div className="rounded-card border border-line bg-card p-4">
      <h2 className="text-xs font-medium uppercase tracking-wide text-ink-muted">
        {COPY.stepper.heading}
      </h2>
      {done < 0 && !running ? (
        <p className="mt-2 text-sm text-ink-muted">{COPY.stepper.idle}</p>
      ) : (
        <ol className="mt-3 space-y-1.5">
          {STEPS.map((step, i) => {
            const isDone = i <= done;
            const isActive = i === activeIdx && done < 6;
            return (
              <li key={step.id} className="flex items-center gap-2 text-sm">
                <span
                  className={`flex h-4 w-4 items-center justify-center rounded-full border text-[9px] ${
                    isDone
                      ? "border-olive bg-olive text-white"
                      : isActive
                        ? "animate-pulse border-gold-deep bg-gold/20"
                        : "border-line-strong bg-canvas"
                  }`}
                >
                  {isDone ? "✓" : ""}
                </span>
                <span
                  className={
                    isDone
                      ? "text-ink"
                      : isActive
                        ? "font-medium text-gold-deep"
                        : "text-ink-subtle"
                  }
                >
                  {step.label}
                </span>
              </li>
            );
          })}
        </ol>
      )}
      {workLog.length > 0 && (
        <div className="mt-3 border-t border-line pt-2">
          <ul className="space-y-1 font-mono text-[10px] leading-relaxed text-ink-muted">
            {workLog.slice(-4).map((entry, i) => (
              <li key={i} className="truncate" title={entry}>
                {entry}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
