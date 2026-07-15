import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.API_KEY || "";

const ALLOWED_PREFIXES = [
  "/api/v1/runs",
  "/api/v1/monitoring",
  "/api/v1/analyze",
  "/api/v1/extractions",
  "/api/v1/qa",
  "/api/v1/guardrails",
  "/api/v1/health",
  "/api/v1/costs",
  "/api/v1/harness",
  "/api/v1/loop",
  "/api/v1/batch",
  "/api/v1/webhooks",
];

const ALLOWED_RESPONSE_HEADERS = new Set([
  "content-type",
  "content-length",
  "cache-control",
]);

async function proxyRequest(
  request: NextRequest,
  path: string[]
) {
  const targetPath = `/api/${path.join("/")}`;
  if (!ALLOWED_PREFIXES.some((p) => targetPath.startsWith(p))) {
    return NextResponse.json({ detail: "Forbidden" }, { status: 403 });
  }
  const targetUrl = new URL(targetPath, BACKEND_URL);

  request.nextUrl.searchParams.forEach((value, key) => {
    targetUrl.searchParams.set(key, value);
  });

  const headers = new Headers();
  headers.set("X-API-Key", API_KEY);
  headers.set("Content-Type", request.headers.get("Content-Type") || "application/json");

  const init: RequestInit = {
    method: request.method,
    headers,
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
          } catch (err) {
            controller.error(err);
          } finally {
            controller.close();
          }
        },
      });

      return new NextResponse(stream, {
        status: res.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
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

    return new NextResponse(body, {
      status: res.status,
      statusText: res.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    return NextResponse.json(
      { detail: `Proxy error: ${error instanceof Error ? error.message : "unknown"}` },
      { status: 502 }
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
