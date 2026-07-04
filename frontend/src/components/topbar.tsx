"use client";

import { usePathname } from "next/navigation";

const PAGE_TITLES: Record<string, string> = {
  "/": "Overview",
  "/runs": "Runs",
  "/settings": "Settings",
};

export function Topbar() {
  const pathname = usePathname();
  const title = PAGE_TITLES[pathname] || "VoiceScope";

  return (
    <div className="topbar">
      <span className="topbar-title">{title}</span>
      <div className="topbar-spacer" />
      <div className="topbar-status">
        <div className="status-dot" />
        <span>pipeline healthy</span>
      </div>
    </div>
  );
}
