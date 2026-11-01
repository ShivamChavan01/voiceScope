import { createHash, timingSafeEqual } from "node:crypto";

type Credentials = { username: string | undefined; password: string | undefined };

export function operatorAccess(
  request: Request,
  credentials: Credentials = {
    username: process.env.OPERATOR_AUTH_USER,
    password: process.env.OPERATOR_AUTH_PASSWORD,
  },
): Response | null {
  const headers = { "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "X-Frame-Options": "DENY" };
  const { username, password } = credentials;
  const url = new URL(request.url);
  // NextURL canonicalizes loopback IPs to localhost. Recover the wire host only
  // for explicit loopback authorities on the same port; aliases remain distinct.
  const host = request.headers.get("host");
  if (url.hostname === "localhost" && host && /^(?:localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?$/i.test(host)) {
    try {
      const wireOrigin = new URL(`${url.protocol}//${host}`);
      if (wireOrigin.port === url.port) url.hostname = wireOrigin.hostname;
    } catch {
      return Response.json({ detail: "Invalid request authority." }, { status: 403, headers });
    }
  }
  if (url.protocol !== "https:" && !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
    return Response.json({ detail: "HTTPS is required." }, { status: 403, headers });
  }
  const origin = request.headers.get("origin");
  const documentNavigation = ["GET", "HEAD"].includes(request.method)
    && request.headers.get("sec-fetch-mode") === "navigate"
    && request.headers.get("sec-fetch-dest") === "document";
  if ((request.headers.get("sec-fetch-site") === "cross-site" && !documentNavigation) || (origin && origin !== url.origin)) {
    return Response.json({ detail: "Cross-origin access is forbidden." }, { status: 403, headers });
  }
  // Public access is limited to an explicitly synthetic Vercel Preview.
  // Production never takes this path, even if these flags are copied there.
  if (process.env.PUBLIC_SYNTHETIC_DEMO === "true"
      && process.env.STAGING_DEMO_ONLY === "true"
      && process.env.VERCEL_ENV === "preview") {
    return null;
  }
  if (!username || username.includes(":") || !password || password.length < 24) {
    return Response.json({ detail: "Private operator access is not configured." }, { status: 503, headers });
  }
  const authorization = request.headers.get("authorization") || "";
  const match = /^Basic ([A-Za-z0-9+/]+={0,2})$/i.exec(authorization);
  if (match && authorization.length <= 8192) {
    const supplied = Buffer.from(match[1], "base64");
    const expected = Buffer.from(`${username}:${password}`, "utf8");
    if (timingSafeEqual(createHash("sha256").update(supplied).digest(), createHash("sha256").update(expected).digest())) {
      return null;
    }
  }
  return Response.json({ detail: "Operator authentication required." }, {
    status: 401,
    headers: { ...headers, "WWW-Authenticate": 'Basic realm="VoiceScope private operator", charset="UTF-8"' },
  });
}
