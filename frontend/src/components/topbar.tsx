"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const PAGE_TITLES: Record<string, string> = {
  "/": "Overview",
  "/runs": "Runs",
  "/settings": "Settings",
};

export function Topbar() {
  const pathname = usePathname();
  const title = PAGE_TITLES[pathname] || "VoiceScope";
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    const check = () =>
      fetch("/api/v1/health")
        .then((r) => r.ok)
        .then(setHealthy)
        .catch(() => setHealthy(false));
    check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="topbar">
      <span className="topbar-title">{title}</span>
      <div className="topbar-spacer" />
      <div className="topbar-status" aria-live="polite">
        <div className={`status-dot ${healthy === false ? "status-dot-error" : ""}`} />
        <span>{healthy === null ? "checking..." : healthy ? "pipeline healthy" : "pipeline unreachable"}</span>
      </div>
    </div>
  );
}
