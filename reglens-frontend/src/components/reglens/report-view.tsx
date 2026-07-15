import ReactMarkdown from "react-markdown";
import { COPY } from "@/lib/reglens/copy";

export function ReportView({ report }: { report?: string }) {
  if (!report) return null;
  return (
    <div className="rounded-card border border-line bg-card p-5">
      <h2 className="font-display text-base text-ink">{COPY.report.heading}</h2>
      <div className="reglens-report mt-2 max-w-[72ch] text-sm text-ink">
        <ReactMarkdown>{report}</ReactMarkdown>
      </div>
    </div>
  );
}
