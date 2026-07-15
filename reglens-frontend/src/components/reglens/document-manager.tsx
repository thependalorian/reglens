"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DocumentRow } from "@/lib/reglens/types";
import { COPY } from "@/lib/reglens/copy";
import { logger } from "@/lib/reglens/logger";

const STATUS_STYLE: Record<string, string> = {
  active: "bg-olive/12 text-olive",
  processing: "bg-gold-deep/12 text-gold-deep",
  failed: "bg-burgundy/12 text-burgundy",
};

export function DocumentManager() {
  const [docs, setDocs] = useState<DocumentRow[] | null>(null);
  const [error, setError] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/backend/api/reglens/documents");
      const d = await r.json();
      setDocs(d.documents ?? []);
      setError(false);
    } catch (e) {
      logger.error("documents load failed", e);
      setError(true);
    }
  }, []);

  useEffect(() => {
    // Fetch the pipeline on mount; load() is async, so state updates happen
    // in its promise callback (after await), not synchronously in the effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  // Poll while any document is still processing.
  useEffect(() => {
    if (!docs?.some((d) => d.status === "processing")) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [docs, load]);

  const upload = async (file: File) => {
    setUploading(true);
    setNotice(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await fetch("/api/backend/api/reglens/documents", { method: "POST", body: form });
      const d = await r.json();
      if (d.status === "skipped") setNotice(COPY.documents.skipped);
      await load();
    } catch (e) {
      logger.error("upload failed", e);
      setNotice(COPY.common.error);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const remove = async (doc: DocumentRow) => {
    if (!confirm(COPY.documents.confirmRemove)) return;
    try {
      await fetch(`/api/backend/api/reglens/documents/${doc.document_uid}`, { method: "DELETE" });
      await load();
    } catch (e) {
      logger.error("delete failed", e);
    }
  };

  const totalChunks = (docs ?? []).reduce((s, d) => s + d.chunk_count, 0);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-lg text-ink">{COPY.documents.heading}</h2>
          <p className="mt-0.5 text-xs text-ink-muted">{COPY.documents.subheading}</p>
        </div>
        <div className="flex items-center gap-3">
          {docs && (
            <span className="text-xs text-ink-muted">
              {COPY.documents.totals(docs.length, totalChunks)}
            </span>
          )}
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.docx,.txt,.md,.pptx,.xlsx,.html,.htm"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f);
            }}
          />
          <button
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
            className="rounded-pill bg-burgundy px-4 py-1.5 text-sm font-medium text-on-burgundy transition-colors hover:bg-burgundy-deep disabled:opacity-50"
          >
            {uploading ? COPY.documents.uploading : COPY.documents.upload}
          </button>
        </div>
      </header>

      {notice && <p className="text-xs text-gold-deep">{notice}</p>}
      {error && <p className="text-sm text-burgundy">{COPY.documents.error}</p>}

      {docs && docs.length === 0 && !error && (
        <p className="text-sm text-ink-subtle">{COPY.documents.empty}</p>
      )}

      {docs && docs.length > 0 && (
        <div className="overflow-x-auto rounded-card border border-line bg-card">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-3 py-2.5 font-medium">{COPY.documents.colTitle}</th>
                <th className="px-3 py-2.5 font-medium">{COPY.documents.colBody}</th>
                <th className="px-3 py-2.5 font-medium">{COPY.documents.colDomain}</th>
                <th className="px-3 py-2.5 text-right font-medium">{COPY.documents.colChunks}</th>
                <th className="px-3 py-2.5 font-medium">{COPY.documents.colStatus}</th>
                <th className="px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.document_uid} className="border-b border-line last:border-0">
                  <td className="px-3 py-2.5 text-ink">
                    {d.title}
                    {d.error ? (
                      <span className="block text-xs text-burgundy" title={d.error}>
                        {d.error.slice(0, 80)}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2.5 text-ink-muted">{d.regulatory_body}</td>
                  <td className="px-3 py-2.5 text-ink-muted">{d.domain}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-ink-muted">{d.chunk_count}</td>
                  <td className="px-3 py-2.5">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[d.status] ?? STATUS_STYLE.failed}`}
                    >
                      {d.status === "processing" && (
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
                      )}
                      {COPY.documents.status[d.status] ?? d.status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <button
                      onClick={() => remove(d)}
                      className="text-xs text-ink-muted transition-colors hover:text-burgundy"
                    >
                      {COPY.documents.remove}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
