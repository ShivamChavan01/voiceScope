"use client";

import React from "react";

const HARNESS_LAYERS = [
  { id: "schema", name: "Schema", weight: 0.33 },
  { id: "citations", name: "Citations", weight: 0.17 },
  { id: "facts", name: "Facts", weight: 0.17 },
  { id: "sentiment_consistency", name: "Sentiment", weight: 0.11 },
  { id: "outcome_evidence", name: "Outcome", weight: 0.11 },
  { id: "escalation", name: "Escalation", weight: 0.06 },
  { id: "duplicate", name: "Duplicate", weight: 0.05 },
];

export const HARNESS_NAMES = HARNESS_LAYERS.map((l) => l.name);
export const HARNESS_KEYS = HARNESS_LAYERS.map((l) => l.id);

function getStatus(score: number): "pass" | "warning" | "fail" | "na" {
  if (score === 0) return "na";
  if (score >= 80) return "pass";
  if (score >= 50) return "warning";
  return "fail";
}

function statusLabel(status: string) {
  if (status === "pass") return "Pass";
  if (status === "warning") return "Warn";
  if (status === "fail") return "Fail";
  return "N/A";
}

interface HarnessBarProps {
  scores: number[];
  runId?: string;
  runLabel?: string;
  onOpenRun?: (id: string) => void;
  mini?: boolean;
}

export function HarnessBar({ scores, runId, runLabel, onOpenRun, mini }: HarnessBarProps) {
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

  if (mini) {
    return (
      <div className="mini-harness" ref={rowsRef}>
        <div className="harness-row" style={{ height: 8 }}>
          {layers.map((l, i) => (
            <div
              key={i}
              className="seg"
              data-status={l.status}
              style={{ width: `${l.weight * 100}%` }}
              aria-label={`${l.name}: ${l.score}`}
            />
          ))}
        </div>
      </div>
    );
  }

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
      {/* Labels row */}
      <div className="harness-labels">
        {layers.map((l, i) => (
          <span
            key={`l${i}`}
            className={`harness-label ${hl === i ? "hl" : ""}`}
            style={{ width: `${l.weight * 100}%` }}
            onMouseEnter={() => !touchMode && setHighlight(i)}
            onMouseLeave={() => !touchMode && clearHighlight()}
          >
            {l.name}
          </span>
        ))}
      </div>

      {/* Expand panel */}
      {hl !== null && (
        <div className="harness-expand show">
          <div className="expand-header">
            <span>Layer</span>
            <span>Weight</span>
            <span style={{ width: 100, textAlign: "center" }}>Bars</span>
            <span>Score</span>
            <span>Status</span>
          </div>
          {layers.map((l, i) => (
            <div key={i} className="expand-layer">
              <span className="expand-name">{l.name}</span>
              <span className="expand-weight">{(l.weight * 100).toFixed(0)}%</span>
              <div className="expand-bars">
                <div className="expand-bar weight" style={{ width: `${l.weight * 100}%` }} />
                <div className="expand-bar" data-status={l.status} style={{ width: `${l.weight * 100}%` }} />
              </div>
              <span className={`expand-score ${l.status}`}>{l.status === "na" ? "N/A" : `${l.score}`}</span>
              <span className={`expand-status-badge badge badge-${l.status === "pass" ? "pass" : l.status === "warning" ? "flag" : l.status === "fail" ? "fail" : "na"}`}>
                {statusLabel(l.status)}
              </span>
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
