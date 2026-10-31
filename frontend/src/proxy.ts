import { NextRequest, NextResponse } from "next/server";
import { operatorAccess } from "@/lib/operator-auth";

export function proxy(request: NextRequest) {
  const denied = operatorAccess(request);
  if (denied) return denied;
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  response.headers.set("X-Frame-Options", "DENY");
  return response;
}

export const config = { matcher: "/:path*" };
