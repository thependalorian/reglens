"use client";

import { useEffect, useState } from "react";
import {
  CopilotChat,
  CopilotChatConfigurationProvider,
  useConfigureSuggestions,
  useInterrupt,
} from "@copilotkit/react-core/v2";

import { ExampleLayout } from "@/components/example-layout";
import { ReglensCanvas } from "@/components/reglens/canvas";
import { FindingsReviewPanel } from "@/components/reglens/findings-review-panel";
import type { FindingsReviewPayload, ReviewDecision } from "@/lib/reglens/types";

const THREAD_KEY = "reglens.threadId";

/** The LangGraph `interrupt(...)` value can reach the client in a few shapes
 *  depending on how AG-UI / CopilotKit serialize it: the payload object
 *  directly, a JSON string of it, or a single-element array of interrupts.
 *  Normalize all three to the findings_review payload so the panel never
 *  dereferences an undefined `findings`. */
function normalizeInterruptValue(value: unknown): FindingsReviewPayload {
  let v = value;
  if (typeof v === "string") {
    try {
      v = JSON.parse(v);
    } catch {
      v = {};
    }
  }
  if (Array.isArray(v)) v = v[0];
  // LangGraph interrupt objects sometimes nest the payload under `.value`.
  if (v && typeof v === "object" && "value" in v && !("findings" in v)) {
    v = (v as { value: unknown }).value;
  }
  return (v ?? {}) as FindingsReviewPayload;
}

/** Stable thread id persisted in localStorage. Combined with the backend's
 *  Postgres checkpointer, reloading replays the full conversation history —
 *  persistent chat, fully self-hosted (no managed Threads service). */
function usePersistentThreadId(): string | null {
  const [threadId, setThreadId] = useState<string | null>(null);
  useEffect(() => {
    // localStorage is a browser-only external system, so it must be read
    // after mount (not during render) to stay SSR/hydration-safe — the
    // canonical effect-initializes-from-external-source pattern.
    let id = localStorage.getItem(THREAD_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(THREAD_KEY, id);
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setThreadId(id);
  }, []);
  return threadId;
}

function Workspace() {
  // HITL: the backend hitl_node raises interrupt({type:"findings_review",...}).
  // resolve() resumes the LangGraph run with the reviewer's decision so the
  // graph routes approve -> report, refine -> retrieve, reject -> end.
  useInterrupt({
    render: ({ event, resolve }) => (
      <FindingsReviewPanel
        payload={normalizeInterruptValue(event.value)}
        onDecision={(decision: ReviewDecision) => resolve(decision)}
      />
    ),
  });

  useConfigureSuggestions({
    suggestions: [
      {
        title: "Detect payment-system sludge",
        message:
          "Find overlapping or conflicting obligations across the payment system determinations in the corpus.",
      },
      {
        title: "AML/CFT overlaps",
        message:
          "Where do the AML/CFT obligations in the corpus duplicate or diverge across instruments?",
      },
      {
        title: "E-money vs the Act",
        message:
          "Compare the e-money determination (PSD-3) against the Payment System Management Act for accumulation and conflict.",
      },
    ],
  });

  return (
    <ExampleLayout
      chatContent={<CopilotChat />}
      appContent={<ReglensCanvas />}
    />
  );
}

export default function HomePage() {
  const threadId = usePersistentThreadId();
  if (!threadId) return null; // wait for the persisted id before mounting the thread

  return (
    <CopilotChatConfigurationProvider
      agentId="default"
      threadId={threadId}
      hasExplicitThreadId
    >
      <div className="h-full">
        <Workspace />
      </div>
    </CopilotChatConfigurationProvider>
  );
}
