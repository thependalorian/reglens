"use client";

import { useState } from "react";
import { useAgent } from "@copilotkit/react-core/v2";
import type { ReglensAgentState } from "@/lib/reglens/types";
import { COPY } from "@/lib/reglens/copy";
import { WorkflowStepper } from "./workflow-stepper";
import { CoverageMeter } from "./coverage-meter";
import { AnalysisCharts } from "./analysis-charts";
import { ReportView } from "./report-view";
import { FindingCard } from "./finding-card";
import { DocumentManager } from "./document-manager";

type Tab = "analysis" | "documents";

export function ReglensCanvas() {
  const [tab, setTab] = useState<Tab>("analysis");
  const { agent } = useAgent({ agentId: "default" });
  const state = (agent?.state ?? {}) as ReglensAgentState;
  const running = Boolean(
    (agent as { isRunning?: boolean } | undefined)?.isRunning,
  );

  // Show findings inline in the canvas once detection has produced them
  // (the interactive review happens in the chat interrupt panel).
  const findings = state.sludge_findings ?? [];
  const reviewing = state.status === "awaiting_review";

  return (
    <div className="flex h-full flex-col bg-canvas">
      <div className="flex shrink-0 items-center gap-1 px-5 pt-4 pb-3">
        <div className="inline-flex gap-1 rounded-pill border border-line bg-card p-1">
          {(["analysis", "documents"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-pill px-4 py-1.5 text-sm transition-colors ${
                tab === t
                  ? "bg-burgundy font-medium text-on-burgundy"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {COPY.tabs[t]}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 pb-6">
        {tab === "analysis" ? (
          <div className="space-y-4">
            <WorkflowStepper state={state} running={running} />
            <CoverageMeter coverage={state.coverage} />
            <AnalysisCharts findings={findings} />
            {findings.length > 0 && (
              <div className="space-y-3">
                <h2 className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                  {reviewing ? COPY.review.heading : COPY.tabs.analysis}
                </h2>
                {findings.map((f) => (
                  <FindingCard
                    key={f.finding_id}
                    finding={f}
                    grounding={state.grounding?.findings?.[f.finding_id]}
                  />
                ))}
              </div>
            )}
            <ReportView report={state.final_report} />
          </div>
        ) : (
          <DocumentManager />
        )}
      </div>
    </div>
  );
}
