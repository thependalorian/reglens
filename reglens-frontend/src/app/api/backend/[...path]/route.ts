/**
 * Authenticated proxy to the FastAPI backend for the non-CopilotKit surfaces
 * (document management, corpus, health, precheck/compare SSE). Keeps
 * REGLENS_API_TOKEN server-side.
 */
import { NextRequest } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL || process.env.AGENT_URL || "http://localhost:8058";
const token = process.env.REGLENS_API_TOKEN || "";

// Exact paths (GET/POST/DELETE) reachable through the proxy.
const ALLOWED_EXACT = [
  "health",
  "api/reglens/corpus",
  "api/reglens/usecases",
  "api/reglens/documents",
  "api/reglens/precheck",
  "api/reglens/compare",
];
// Prefix match for DELETE /api/reglens/documents/{uid}
const ALLOWED_PREFIX = ["api/reglens/documents/"];

function backendUrl(path: string[]): string | null {
  const joined = path.join("/");
  if (ALLOWED_EXACT.includes(joined)) return `${BACKEND_URL}/${joined}`;
  if (ALLOWED_PREFIX.some((p) => joined.startsWith(p)))
    return `${BACKEND_URL}/${joined}`;
  return null;
}

function auth(extra: Record<string, string> = {}): HeadersInit {
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
) {
  const { path } = await ctx.params;
  const url = backendUrl(path);
  if (!url) return new Response("Not found", { status: 404 });
  const upstream = await fetch(url, { headers: auth() });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
    },
  });
}

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
) {
  const { path } = await ctx.params;
  const url = backendUrl(path);
  if (!url) return new Response("Not found", { status: 404 });

  const contentType = req.headers.get("Content-Type") ?? "";
  // Multipart (document upload) must pass the raw body + boundary through.
  const isMultipart = contentType.startsWith("multipart/form-data");

  const upstream = await fetch(url, {
    method: "POST",
    headers: auth(isMultipart ? { "Content-Type": contentType } : { "Content-Type": "application/json" }),
    body: isMultipart ? await req.arrayBuffer() : await req.text(),
    // @ts-expect-error duplex required by Node fetch for streamed bodies
    duplex: "half",
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
      "Cache-Control": "no-cache",
    },
  });
}

export async function DELETE(
  _req: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
) {
  const { path } = await ctx.params;
  const url = backendUrl(path);
  if (!url) return new Response("Not found", { status: 404 });
  const upstream = await fetch(url, { method: "DELETE", headers: auth() });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
    },
  });
}
