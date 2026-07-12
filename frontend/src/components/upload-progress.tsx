"use client";

import { StreamEvent } from "@/lib/api";
import { Mic, Brain, FileText, Check, AlertCircle } from "lucide-react";

const STAGES = [
  { key: "transcription", label: "Transcribing", icon: Mic },
  { key: "analysis", label: "Analyzing", icon: Brain },
  { key: "report", label: "Reporting", icon: FileText },
] as const;

interface UploadProgressProps {
  events: StreamEvent[];
  error?: string;
}

export function UploadProgress({ events, error }: UploadProgressProps) {
  const completedStages = new Set(
    events
      .filter((e) => e.event === "stage_complete")
      .map((e) => e.stage)
  );
  const isComplete = events.some((e) => e.event === "complete");
  const lastEvent = events[events.length - 1];
  const hasStarted = events.some((e) => e.event === "started");

  if (!hasStarted && !error) return null;

  return (
    <div className="upload-progress">
      {STAGES.map(({ key, label, icon: Icon }, i) => {
        const done = completedStages.has(key);
        const active =
          !done &&
          !isComplete &&
          events.some(
            (e) =>
              e.event === "started" ||
              (e.event === "stage_complete" &&
                STAGES.findIndex((s) => s.key === e.stage) < i)
          ) &&
          !completedStages.has(
            STAGES[Math.min(i + 1, STAGES.length - 1)].key
          );

        return (
          <div
            key={key}
            className={`upload-stage ${done ? "done" : ""} ${active ? "active" : ""}`}
          >
            <div className="upload-stage-icon">
              {done ? (
                <Check className="h-4 w-4" />
              ) : (
                <Icon className="h-4 w-4" />
              )}
            </div>
            <span className="upload-stage-label">{label}</span>
          </div>
        );
      })}

      {isComplete && lastEvent?.result && (
        <div className="upload-stage done">
          <div className="upload-stage-icon">
            <Check className="h-4 w-4" />
          </div>
          <span className="upload-stage-label">Done</span>
        </div>
      )}

      {error && (
        <div className="upload-stage error">
          <div className="upload-stage-icon">
            <AlertCircle className="h-4 w-4" />
          </div>
          <span className="upload-stage-label">Error: {error}</span>
        </div>
      )}
    </div>
  );
}
