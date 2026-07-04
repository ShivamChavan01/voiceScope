"use client";

import React from "react";

const HARNESS_LAYERS = [
  { id: "transcription", name: "Transcription Quality", weight: 0.10 },
  { id: "entity", name: "Entity Extraction", weight: 0.08 },
  { id: "intent", name: "Intent Classification", weight: 0.08 },
  { id: "sentiment", name: "Sentiment Analysis", weight: 0.06 },
  { id: "topic", name: "Topic Segmentation", weight: 0.07 },
  { id: "consistency", name: "Factual Consistency", weight: 0.12 },
  { id: "coherence", name: "Coherence Score", weight: 0.08 },
  { id: "resolution", name: "Resolution Detection", weight: 0.09 },
  { id: "compliance", name: "Compliance Check", weight: 0.10 },
  { id: "hallucination", name: "Hallucination Detection", weight: 0.11 },
  { id: "latency", name: "Response Latency", weight: 0.05 },
  { id: "safety", name: "Safety & Harm", weight: 0.04 },
  { id: "completion", name: "Completion", weight: 0.02 },
];

export const HARNESS_NAMES = HARNESS_LAYERS.map((l) => l.name);

function getStatus(score: number): "pass" | "warning" | "fail" {
  if (score >= 80) return "pass";
  if (score >= 50) return "warning";
  return "fail";
}

function statusColor(status: string) {
  if (status === "pass") return "var(--success)";
  if (status === "warning") return "var(--warning)";
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
  const flagged = layers.filter((l) => l.status !== "pass").length;

  const setHighlight = (idx: number) => {
    setHl(idx);
    if (rowsRef.current) {
      rowsRef.current.classList.add("has-highlight");
      const segs = rowsRef.current.querySelectorAll<HTMLElement>(".seg");
      segs.forEach((s, i) => {
        const si = Math.floor(i / 13);
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
              <span className={`expand-score ${l.status}`}>{l.score.toFixed(2)}</span>
            </div>
          ))}
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="harness-caption">
              13 layers · <span className="flagged">{flagged}</span> flagged
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
