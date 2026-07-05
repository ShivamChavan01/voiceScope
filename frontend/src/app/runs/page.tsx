"use client";

import { useState, useEffect, useCallback } from "react";
import { HarnessBar, HARNESS_NAMES, HARNESS_KEYS } from "@/components/harness-bar";
import {
  getRuns,
  getRun,
  analyzeAudio,
  type Run,
} from "@/lib/api";

function UploadIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width={20} height={20} style={{ marginBottom: 8, opacity: 0.5 }}>
      <path d="M8 10V3M5 5l3-3 3 3M2 11v2a1 1 0 001 1h10a1 1 0 001-1v-2" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width={14} height={14}>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5L14 14" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M3 3l8 8M11 3l-8 8" />
    </svg>
  );
}

function relativeTime(dateStr: string) {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr + "Z").getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function formatDuration(seconds: number | null) {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${String(s).padStart(2, "0")}s` : `${s}s`;
}

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [drawerTab, setDrawerTab] = useState<"harness" | "transcript" | "report">("harness");
  const [search, setSearch] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const fetchRuns = useCallback(async () => {
    try {
      const params: Record<string, string | number> = { limit: 50 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      const res = await getRuns(params);
      setRuns(res.runs);
      setTotal(res.total);
    } catch {
      setRuns([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      await analyzeAudio(file);
      await fetchRuns();
    } catch (err) {
      console.error("Analysis failed:", err);
    } finally {
      setUploading(false);
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  };

  const openRun = async (run: Run) => {
    try {
      const detail = await getRun(run.run_id);
      setSelectedRun(detail);
    } catch {
      setSelectedRun({ ...run, transcript_preview: "Transcript unavailable" } as Run);
    }
    setDrawerTab("harness");
    setDrawerOpen(true);
  };

  const scoreColor = (score: number | null) => {
    if (score == null) return "text-muted";
    if (score >= 0.8) return "text-success";
    if (score >= 0.5) return "text-warning";
    return "text-danger";
  };

  const filtered = runs.filter((r) => {
    if (platformFilter && r.provider !== platformFilter) return false;
    return true;
  });

  function harnessScoresForRun(run: Run): number[] {
    if (!run.layer_scores) return Array(HARNESS_KEYS.length).fill(0);
    return HARNESS_KEYS.map((k) => {
      const v = run.layer_scores?.[k];
      return v != null ? Math.round(v * 100) : 0;
    });
  }

  return (
    <>
      {/* Upload */}
      <div
        className="upload-area"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleFileDrop}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept="audio/*"
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />
        <UploadIcon />
        <div>{uploading ? "Analyzing..." : "Drop audio file or click to analyze"}</div>
      </div>

      {/* Filters */}
      <div className="filter-row">
        <div className="f-row" style={{ position: "relative" }}>
          <SearchIcon />
          <input
            className="filter-input"
            placeholder="Search runs..."
            style={{ paddingLeft: 4 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="filter-input" style={{ minWidth: 100 }} value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)}>
          <option value="">All platforms</option>
          <option value="openai">OpenAI</option>
          <option value="gemini">Gemini</option>
          <option value="anthropic">Anthropic</option>
        </select>
        <select className="filter-input" style={{ minWidth: 90 }} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All status</option>
          <option value="completed">Completed</option>
          <option value="partial">Partial</option>
          <option value="failed">Failed</option>
        </select>
        <div className="filter-sep" />
        <span className="text-muted" style={{ fontSize: 12 }}>{filtered.length} runs</span>
      </div>

      {/* Table */}
      <div className="table-wrap">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Intent</th>
                <th>Sentiment</th>
                <th>Duration</th>
                <th>Score</th>
                <th>Status</th>
                <th>Provider</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>Loading...</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>No runs found</td></tr>
              ) : (
                filtered.map((run) => (
                  <tr key={run.run_id} onClick={() => openRun(run)}>
                    <td><span className="mono text-accent">{run.run_id.slice(0, 12)}</span></td>
                    <td><span className="text-secondary">{run.intent || "—"}</span></td>
                    <td><span className="text-secondary">{run.sentiment || "—"}</span></td>
                    <td><span className="mono text-secondary">{formatDuration(run.duration_seconds)}</span></td>
                    <td><span className={`mono ${scoreColor(run.truth_score)}`}>{run.truth_score != null ? run.truth_score.toFixed(2) : "—"}</span></td>
                    <td>
                      <span className={`badge ${run.status === "completed" ? "badge-pass" : run.status === "failed" ? "badge-fail" : "badge-flag"}`}>
                        {run.status}
                      </span>
                    </td>
                    <td><span className="mono text-muted">{run.provider || "—"}</span></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Drawer overlay */}
      <div className={`drawer-overlay ${drawerOpen ? "open" : ""}`} onClick={() => setDrawerOpen(false)} />

      {/* Drawer */}
      <div className={`drawer ${drawerOpen ? "open" : ""}`}>
        <div className="drawer-header">
          <span className="drawer-title mono">{selectedRun?.run_id?.slice(0, 12) || ""}</span>
          <span className={`badge ${selectedRun?.status === "completed" ? "badge-pass" : selectedRun?.status === "failed" ? "badge-fail" : "badge-flag"}`}>
            {selectedRun?.status || ""}
          </span>
          <button className="drawer-close" onClick={() => setDrawerOpen(false)}>
            <CloseIcon />
          </button>
        </div>

        <div className="drawer-tabs">
          {(["harness", "transcript", "report"] as const).map((tab) => (
            <button
              key={tab}
              className={`drawer-tab ${drawerTab === tab ? "active" : ""}`}
              onClick={() => setDrawerTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        <div className="drawer-body">
          {drawerTab === "harness" && selectedRun && (
            <div>
              <div className="detail-grid">
                <div className="detail-cell">
                  <div className="detail-label">Score</div>
                  <div className="detail-value text-accent">{selectedRun.truth_score != null ? selectedRun.truth_score.toFixed(2) : "—"}</div>
                </div>
                <div className="detail-cell">
                  <div className="detail-label">Duration</div>
                  <div className="detail-value">{formatDuration(selectedRun.duration_seconds)}</div>
                </div>
                <div className="detail-cell">
                  <div className="detail-label">Provider</div>
                  <div className="detail-value">{selectedRun.provider || "—"}</div>
                </div>
                <div className="detail-cell">
                  <div className="detail-label">Started</div>
                  <div className="detail-value">{relativeTime(selectedRun.created_at)}</div>
                </div>
              </div>

              <div style={{ marginBottom: 16 }}>
                <div className="section-title" style={{ marginBottom: 8 }}>Validation Harness</div>
                <HarnessBar scores={harnessScoresForRun(selectedRun)} />
              </div>

              <div className="harness-layers">
                {HARNESS_NAMES.map((name, i) => {
                  const score = harnessScoresForRun(selectedRun)[i] || 0;
                  const status = score >= 80 ? "pass" : score >= 50 ? "warning" : "fail";
                  const color = status === "pass" ? "var(--success)" : status === "warning" ? "var(--warning)" : "var(--destructive)";
                  return (
                    <div key={i} className="harness-layer">
                      <span className="harness-layer-name">{name}</span>
                      <div className="harness-layer-bar">
                        <div className="harness-layer-fill" style={{ width: `${score}%`, background: color }} />
                      </div>
                      <span className={`harness-layer-score text-${status === "pass" ? "success" : status === "warning" ? "warning" : "danger"}`}>{score}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {drawerTab === "transcript" && selectedRun && (
            <div>
              {selectedRun.transcript_speakers && selectedRun.transcript_speakers.length > 1 ? (
                <div className="transcript-speakers">
                  {selectedRun.transcript_speakers.map((seg, i) => (
                    <div key={i} className="transcript-turn">
                      <span className={`speaker-badge speaker-${seg.role || "other"}`}>
                        {seg.label || seg.role || `Speaker ${seg.speaker}`}
                      </span>
                      <span className="transcript-text">{seg.text}</span>
                    </div>
                  ))}
                </div>
              ) : selectedRun.transcript_preview ? (
                <div className="transcript-text" style={{ whiteSpace: "pre-wrap" }}>
                  {selectedRun.transcript_preview}
                </div>
              ) : (
                <div className="empty-state">No transcript available</div>
              )}
            </div>
          )}

          {drawerTab === "report" && selectedRun && (
            <div>
              {selectedRun.intent ? (
                <div className="detail-grid">
                  <div className="detail-cell">
                    <div className="detail-label">Intent</div>
                    <div className="detail-value">{selectedRun.intent}</div>
                  </div>
                  <div className="detail-cell">
                    <div className="detail-label">Sentiment</div>
                    <div className="detail-value">{selectedRun.sentiment || "—"}</div>
                  </div>
                  <div className="detail-cell">
                    <div className="detail-label">Outcome</div>
                    <div className="detail-value">{selectedRun.outcome || "—"}</div>
                  </div>
                  <div className="detail-cell">
                    <div className="detail-label">Hallucination</div>
                    <div className="detail-value">{selectedRun.hallucination_detected ? "Detected" : "None"}</div>
                  </div>
                  <div className="detail-cell">
                    <div className="detail-label">Escalation</div>
                    <div className="detail-value">{selectedRun.escalation_signal ? "Yes" : "No"}</div>
                  </div>
                  <div className="detail-cell">
                    <div className="detail-label">Model</div>
                    <div className="detail-value">{selectedRun.model || "—"}</div>
                  </div>
                </div>
              ) : (
                <div className="empty-state">No report data available</div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
