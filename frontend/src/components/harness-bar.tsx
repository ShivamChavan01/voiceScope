"use client";

import React from "react";

const HARNESS_LAYERS = [
  { id: "schema", name: "Schema Validation", weight: 0.30 },
  { id: "citations", name: "Citation Verification", weight: 0.15 },
  { id: "facts", name: "Fact Extraction", weight: 0.15 },
  { id: "sentiment_consistency", name: "Sentiment Consistency", weight: 0.10 },
  { id: "outcome_evidence", name: "Outcome Evidence", weight: 0.10 },
  { id: "escalation", name: "Escalation Detection", weight: 0.05 },
  { id: "duplicate", name: "Duplicate Detection", weight: 0.05 },
  { id: "cross_check", name: "Cross-Check", weight: 0.10 },
];

export const HARNESS_NAMES = HARNESS_LAYERS.map((l) => l.name);
export const HARNESS_KEYS = HARNESS_LAYERS.map((l) => l.id);
export const HARNESS_WEIGHTS = HARNESS_LAYERS.map((l) => l.weight);

function getStatus(score: number): "pass" | "warning" | "fail" | "na" {
  if (score === 0) return "na";
  if (score >= 80) return "pass";
  if (score >= 50) return "warning";
  return "fail";
}

function statusColor(status: string) {
  if (status === "pass") return "var(--success)";
  if (status === "warning") return "var(--warning)";
  if (status === "na") return "var(--muted-foreground)";
  return "var(--destructive)";
}

interface HarnessBarProps {
  scores: number[];
  runId?: string;
  runLabel?: string;
  onOpenRun?: (id: string) => void;
}

export function HarnessBar({ scores, runId, runLabel, onOpenRun }: HarnessBarProps) {
  const rowsRef = React.useRef<HTMLDivElement>(null);
  const [hl, setHl] = React.useState<number | null>(null);
  const [touchMode, setTouchMode] = React.useState(false);

  const layers = HARNESS_LAYERS.map((l, i) => ({
    ...l,
    score: scores[i] || 0,
    status: getStatus(scores[i] || 0),
  }));
  const flagged = layers.filter((l) => l.status !== "pass" && l.status !== "na").length;
  const active = layers.filter((l) => l.status !== "na").length;

  const setHighlight = (idx: number) => {
    setHl(idx);
    if (rowsRef.current) {
      rowsRef.current.classList.add("has-highlight");
      const segs = rowsRef.current.querySelectorAll<HTMLElement>(".seg");
      segs.forEach((s, i) => {
        const si = Math.floor(i / HARNESS_LAYERS.length);
        s.classList.toggle("hl", si === idx);
      });
    }
  };

  const clearHighlight = () => {
    setHl(null);
    if (rowsRef.current) {
      rowsRef.current.classList.remove("has-highlight");
      rowsRef.current.querySelectorAll<HTMLElement>(".seg").forEach((s) => s.classList.remove("hl"));
    }
  };

  return (
    <div className="harness-rows" ref={rowsRef}>
      {/* Weight row */}
      <div className="harness-row">
        {layers.map((l, i) => (
          <div
            key={`w${i}`}
            className="seg row-weight"
            style={{ width: `${l.weight * 100}%` }}
            role="button"
            tabIndex={0}
            aria-label={`${l.name} weight ${(l.weight * 100).toFixed(0)}%`}
            onMouseEnter={() => !touchMode && setHighlight(i)}
            onMouseLeave={() => !touchMode && clearHighlight()}
            onFocus={() => setHighlight(i)}
            onBlur={clearHighlight}
            onTouchStart={(e) => {
              e.preventDefault();
              setTouchMode(true);
              if (hl === i) clearHighlight();
              else setHighlight(i);
            }}
          />
        ))}
      </div>
      {/* Score row */}
      <div className="harness-row">
        {layers.map((l, i) => (
          <div
            key={`s${i}`}
            className="seg"
            data-status={l.status}
            style={{ width: `${l.weight * 100}%` }}
            role="button"
            tabIndex={0}
            aria-label={`${l.name}, score ${l.score.toFixed(2)}, ${l.status}`}
            onMouseEnter={() => !touchMode && setHighlight(i)}
            onMouseLeave={() => !touchMode && clearHighlight()}
            onFocus={() => setHighlight(i)}
            onBlur={clearHighlight}
            onTouchStart={(e) => {
              e.preventDefault();
              setTouchMode(true);
              if (hl === i) clearHighlight();
              else setHighlight(i);
            }}
          />
        ))}
      </div>

      {/* Expand panel */}
      {hl !== null && (
        <div className="harness-expand show">
          <div className="expand-header">
            <span>Weight</span>
            <span>Bars</span>
            <span>Score</span>
          </div>
          {layers.map((l, i) => (
            <div key={i} className="expand-layer">
              <span className="expand-name">{l.name}</span>
              <div className="expand-bars">
                <div className="expand-bar weight" style={{ width: `${l.weight * 100}%` }} />
                <div className="expand-bar" data-status={l.status} style={{ width: `${l.weight * 100}%` }} />
              </div>
              <span className={`expand-score ${l.status}`}>{l.status === "na" ? "N/A" : l.score.toFixed(2)}</span>
            </div>
          ))}
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="harness-caption">
              {HARNESS_LAYERS.length} layers · <span>{active}</span> active · <span className="flagged">{flagged}</span> flagged
            </span>
            {runId && onOpenRun && (
              <span className="harness-link" onClick={() => onOpenRun(runId)}>
                <span className="rid">{runId}</span>
                <span>{runLabel || ""}</span>
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
