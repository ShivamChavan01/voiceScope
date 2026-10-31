import { NextRequest, NextResponse } from "next/server";
import { operatorAccess } from "@/lib/operator-auth";

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.API_KEY || "";
// Enable only behind operator authentication; the shared public proxy is not an identity boundary.
const STT_REVIEW_ENABLED = process.env.STT_REVIEW_PROXY_ENABLED === "true";

const ALLOWED_PREFIXES = [
  "/api/v1/runs",
  "/api/v1/monitoring",
  "/api/v1/analyze",
  "/api/v1/extractions",
  "/api/v1/qa",
  "/api/v1/guardrails",
  "/api/v1/health",
  "/api/v1/status",
  "/api/v1/costs",
  "/api/v1/harness",
  "/api/v1/loop",
  "/api/v1/batch",
  "/api/v1/webhooks",
  "/api/v1/demo",
  "/api/v1/knowledge",
  "/api/v1/policies",
];

const ALLOWED_RESPONSE_HEADERS = new Set([
  "content-type",
  "cache-control",
]);

async function proxyRequest(
  request: NextRequest,
  path: string[]
) {
  // Check at the data boundary too, independently of Next.js Proxy routing.
  const denied = operatorAccess(request);
  if (denied) return denied;
  let segments: string[];
  try {
    segments = path.map((part) => decodeURIComponent(part));
  } catch {
    return NextResponse.json({ detail: "Forbidden" }, { status: 403 });
  }
  // Validate before URL normalization or the backend's percent decoding can
  // turn an unchecked path into a private recording route.
  if (segments.some((part) => !part || part === "." || part === ".." || /[/\\?#%\u0000-\u0020]/.test(part))) {
    return NextResponse.json({ detail: "Forbidden" }, { status: 403 });
  }
  const targetPath = `/api/${segments.map(encodeURIComponent).join("/")}`;
  if (!ALLOWED_PREFIXES.some((p) => targetPath === p || targetPath.startsWith(`${p}/`))) {
    return NextResponse.json({ detail: "Forbidden" }, { status: 403 });
  }
  if (/^\/api\/v1\/runs\/[^/]+\/stt-review(?:\/|$)/.test(targetPath) && !STT_REVIEW_ENABLED) {
    return NextResponse.json({ detail: "Private STT review requires an access-controlled frontend. This public proxy is disabled for recordings." }, { status: 403 });
  }
  const targetUrl = new URL(targetPath, BACKEND_URL);

  request.nextUrl.searchParams.forEach((value, key) => {
    targetUrl.searchParams.set(key, value);
  });

  const headers = new Headers();
  headers.set("X-API-Key", API_KEY);
  if (STT_REVIEW_ENABLED) headers.set("X-STT-Review", "1");
  headers.set("Content-Type", request.headers.get("Content-Type") || "application/json");

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    const res = await fetch(targetUrl.toString(), init);
    const contentType = res.headers.get("content-type") || "";

    if (contentType.includes("text/event-stream")) {
      const stream = new ReadableStream({
        async start(controller) {
          const reader = res.body?.getReader();
          if (!reader) {
            controller.close();
            return;
          }
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              controller.enqueue(value);
            }
            controller.close();
          } catch (err) {
            controller.error(err);
          } finally {
            reader.releaseLock();
          }
        },
      });

      return new NextResponse(stream, {
        status: res.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-store",
          "Connection": "keep-alive",
        },
      });
    }

    const body = await res.arrayBuffer();
    const responseHeaders: Record<string, string> = {};
    res.headers.forEach((value, key) => {
      if (ALLOWED_RESPONSE_HEADERS.has(key.toLowerCase())) {
        responseHeaders[key] = value;
      }
    });
    responseHeaders["cache-control"] = "no-store";

    if (contentType.startsWith("audio/")) {
      // The proxy buffers the full recording; expose its actual length for media metadata.
      responseHeaders["Content-Length"] = String(body.byteLength);
    }

    return new NextResponse(body, {
      status: res.status,
      statusText: res.statusText,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { detail: "Backend request failed. Check service availability and retry." },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(request, path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(request, path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(request, path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(request, path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(request, path);
}
