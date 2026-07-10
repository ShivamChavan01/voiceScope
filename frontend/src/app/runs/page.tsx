"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { HarnessBar, HARNESS_NAMES, HARNESS_KEYS } from "@/components/harness-bar";
import {
  getRuns,
  getRun,
  analyzeAudio,
  deleteRun,
  type Run,
} from "@/lib/api";

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width={20} height={20} aria-hidden="true">
      <path d="M12 16V4M8 8l4-4 4 4M4 14v3a1 1 0 001 1h14a1 1 0 001-1v-3" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width={14} height={14} aria-hidden="true">
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5L14 14" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
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
  const [statusFilter, setStatusFilter] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLTableRowElement | null>(null);

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

  // Escape key closes drawer
  useEffect(() => {
    if (!drawerOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDrawerOpen(false);
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [drawerOpen]);

  // Focus trap in drawer
  useEffect(() => {
    if (drawerOpen && closeButtonRef.current) {
      closeButtonRef.current.focus();
    }
  }, [drawerOpen]);

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

  const openRun = async (run: Run, trigger: HTMLTableRowElement) => {
    triggerRef.current = trigger;
    try {
      const detail = await getRun(run.run_id);
      setSelectedRun(detail);
    } catch {
      setSelectedRun({ ...run, transcript_preview: "Transcript unavailable" } as Run);
    }
    setDrawerTab("harness");
    setDrawerOpen(true);
  };

  const handleDelete = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    if (!confirm("Delete this run?")) return;
    setDeleting(runId);
    try {
      await deleteRun(runId);
      setRuns((prev) => prev.filter((r) => r.run_id !== runId));
      setTotal((prev) => prev - 1);
    } catch (err) {
      console.error("Delete failed:", err);
    } finally {
      setDeleting(null);
    }
  };

  const scoreColor = (score: number | null) => {
    if (score == null) return "text-muted";
    if (score >= 0.8) return "text-success";
    if (score >= 0.5) return "text-warning";
    return "text-danger";
  };

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
        role="button"
        tabIndex={0}
        aria-label="Upload audio file for analysis"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleFileDrop}
        onClick={() => document.getElementById("file-input")?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); document.getElementById("file-input")?.click(); } }}
      >
        <input
          id="file-input"
          type="file"
          accept="audio/*"
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />
        <div className="upload-area-icon">
          <UploadIcon />
        </div>
        <div className="upload-area-text">{uploading ? "Analyzing..." : "Drop audio file or click to analyze"}</div>
        <div className="upload-area-sub">WAV, MP3, M4A — up to 100 MB</div>
      </div>

      {/* Filters */}
      <div className="filter-row">
        <div className="f-row" style={{ position: "relative" }}>
          <SearchIcon />
          <input
            className="filter-input"
            placeholder="Search runs..."
            aria-label="Search runs"
            style={{ paddingLeft: 4 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="filter-input" style={{ minWidth: 90 }} aria-label="Filter by status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All status</option>
          <option value="completed">Completed</option>
          <option value="partial">Partial</option>
          <option value="failed">Failed</option>
        </select>
        <div className="filter-sep" />
        <span className="text-muted" style={{ fontSize: 12 }}>{runs.length} runs</span>
      </div>

      {/* Table */}
      <div className="table-wrap">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Intent</th>
                <th>Time</th>
                <th>Hallucination</th>
                <th>Score</th>
                <th>Harness</th>
                <th>Duration</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={9} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>Loading...</td></tr>
              ) : runs.length === 0 ? (
                <tr><td colSpan={9} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>No runs found</td></tr>
              ) : (
                runs.map((run) => (
                  <tr
                    key={run.run_id}
                    ref={(el) => { if (el) el.onclick = () => openRun(run, el); }}
                    role="button"
                    tabIndex={0}
                    aria-label={`Run ${run.intent || "unknown"}, score ${run.truth_score != null ? `${(run.truth_score * 100).toFixed(0)}%` : "none"}`}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openRun(run, e.currentTarget); } }}
                  >
                    <td><span className="mono text-accent">{run.run_id.slice(0, 12)}</span></td>
                    <td><span className="text-secondary">{run.intent || "—"}</span></td>
                    <td><span className="mono text-muted">{relativeTime(run.created_at)}</span></td>
                    <td>
                      <span
                        className={`hallucination-dot ${run.hallucination_detected ? "detected" : "clean"}`}
                        role="img"
                        aria-label={run.hallucination_detected ? "Hallucination detected" : "No hallucination"}
                        title={run.hallucination_detected ? "Hallucination detected" : "No hallucination"}
                      >
                        {run.hallucination_detected ? "●" : "●"}
                      </span>
                    </td>
                    <td>
                      <span className={`mono ${run.truth_score != null ? (run.hallucination_detected || run.escalation_signal ? "text-danger" : scoreColor(run.truth_score)) : "text-muted"}`}>
                        {run.truth_score != null ? `${(Math.min(run.truth_score, (run.hallucination_detected || run.escalation_signal) ? 0.60 : 1) * 100).toFixed(1)}%` : "—"}
                      </span>
                    </td>
                    <td>
                      <HarnessBar scores={harnessScoresForRun(run)} mini />
                    </td>
                    <td><span className="mono text-secondary">{formatDuration(run.duration_seconds)}</span></td>
                    <td>
                      <span className={`badge ${run.status === "completed" ? "badge-pass" : run.status === "failed" ? "badge-fail" : "badge-flag"}`}>
                        {run.status}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={(e) => handleDelete(e, run.run_id)}
                        disabled={deleting === run.run_id}
                        aria-label="Delete run"
                        style={{ background: "none", border: "none", color: "var(--muted-foreground)", cursor: "pointer", fontSize: 14, padding: "2px 6px", opacity: deleting === run.run_id ? 0.5 : 1 }}
                        title="Delete"
                      >
                        ×
                      </button>
                    </td>
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
      <div
        className={`drawer ${drawerOpen ? "open" : ""}`}
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Run detail: ${selectedRun?.run_id?.slice(0, 12) || ""}`}
      >
        <div className="drawer-header">
          <span className="drawer-title mono">{selectedRun?.run_id?.slice(0, 12) || ""}</span>
          <span className={`badge ${selectedRun?.status === "completed" ? "badge-pass" : selectedRun?.status === "failed" ? "badge-fail" : "badge-flag"}`}>
            {selectedRun?.status || ""}
          </span>
          <button
            className="drawer-close"
            ref={closeButtonRef}
            onClick={() => setDrawerOpen(false)}
            aria-label="Close drawer"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="drawer-tabs" role="tablist">
          {(["harness", "transcript", "report"] as const).map((tab) => (
            <button
              key={tab}
              className={`drawer-tab ${drawerTab === tab ? "active" : ""}`}
              role="tab"
              aria-selected={drawerTab === tab}
              aria-controls={`drawer-panel-${tab}`}
              onClick={() => setDrawerTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        <div className="drawer-body">
          {drawerTab === "harness" && selectedRun && (
            <div id="drawer-panel-harness" role="tabpanel">
              <div className="detail-grid">
                <div className="detail-cell">
                  <div className="detail-label">Score</div>
                  <div className="detail-value" style={{ color: selectedRun.hallucination_detected || selectedRun.escalation_signal ? "var(--destructive)" : "var(--primary)" }}>
                    {selectedRun.truth_score != null ? `${(Math.min(selectedRun.truth_score, (selectedRun.hallucination_detected || selectedRun.escalation_signal) ? 0.60 : 1) * 100).toFixed(1)}%` : "—"}
                    {(selectedRun.hallucination_detected || selectedRun.escalation_signal) && (
                      <span className="badge badge-fail" style={{ marginLeft: 8, fontSize: 10 }}>
                        {selectedRun.hallucination_detected ? "HALLUCINATION" : "ESCALATED"}
                      </span>
                    )}
                  </div>
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
                  const status = score >= 80 ? "pass" : score >= 50 ? "warning" : score === 0 ? "na" : "fail";
                  const color = status === "pass" ? "var(--success)" : status === "warning" ? "var(--warning)" : status === "na" ? "var(--muted-foreground)" : "var(--destructive)";
                  return (
                    <div key={i} className="harness-layer">
                      <span className="harness-layer-name">{name}</span>
                      <div className="harness-layer-bar">
                        <div className="harness-layer-fill" style={{ width: `${score}%`, background: color }} />
                      </div>
                      <span className={`harness-layer-score text-${status === "pass" ? "success" : status === "warning" ? "warning" : status === "na" ? "muted" : "danger"}`}>{score === 0 ? "N/A" : score}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {drawerTab === "transcript" && selectedRun && (
            <div id="drawer-panel-transcript" role="tabpanel">
              {selectedRun.hallucination_detected ? (
                <div className="transcript-hallucination-banner" role="alert">
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width={14} height={14} aria-hidden="true">
                    <path d="M8 2L1.5 13h13L8 2zM8 7v3M8 12h.01" />
                  </svg>
                  <span>Hallucination detected — review flagged claims in the Harness tab</span>
                </div>
              ) : null}
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
            <div id="drawer-panel-report" role="tabpanel">
              {selectedRun.intent ? (
                <>
                  {/* Quality Verdict */}
                  <div className="report-verdict">
                    {selectedRun.hallucination_detected ? (
                      <div className="verdict-box verdict-bad">
                        <div className="verdict-icon">⚠</div>
                        <div>
                          <div className="verdict-title">Hallucination Detected</div>
                          <div className="verdict-sub">The AI agent made claims not supported by the transcript</div>
                        </div>
                      </div>
                    ) : selectedRun.escalation_signal ? (
                      <div className="verdict-box verdict-warn">
                        <div className="verdict-icon">↑</div>
                        <div>
                          <div className="verdict-title">Escalation Required</div>
                          <div className="verdict-sub">The customer asked to speak with a human agent</div>
                        </div>
                      </div>
                    ) : selectedRun.truth_score != null && selectedRun.truth_score >= 0.8 ? (
                      <div className="verdict-box verdict-good">
                        <div className="verdict-icon">✓</div>
                        <div>
                          <div className="verdict-title">Clean Call</div>
                          <div className="verdict-sub">No issues detected — agent followed policy</div>
                        </div>
                      </div>
                    ) : (
                      <div className="verdict-box verdict-ok">
                        <div className="verdict-icon">~</div>
                        <div>
                          <div className="verdict-title">Minor Issues</div>
                          <div className="verdict-sub">Some areas need review but no critical problems</div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Call Summary */}
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
                      <div className="detail-label">Duration</div>
                      <div className="detail-value">{formatDuration(selectedRun.duration_seconds)}</div>
                    </div>
                  </div>

                  {/* Issues Found */}
                  {(() => {
                    const issues: { label: string; detail: string; severity: "bad" | "warn" | "info" }[] = [];
                    const ls = selectedRun.layer_scores || {};

                    if (selectedRun.hallucination_detected) {
                      issues.push({ label: "Hallucination", detail: "Agent made claims not found in the transcript or knowledge base", severity: "bad" });
                    }
                    if (selectedRun.escalation_signal) {
                      issues.push({ label: "Escalation needed", detail: "Customer requested a human agent or supervisor", severity: "warn" });
                    }
                    if (ls.citations != null && ls.citations < 0.7) {
                      issues.push({ label: "Weak citations", detail: `Only ${Math.round(ls.citations * 100)}% of agent claims were backed by transcript evidence`, severity: "warn" });
                    }
                    if (ls.facts != null && ls.facts < 0.7) {
                      issues.push({ label: "Fact mismatch", detail: `Agent stated facts that contradict the transcript (${Math.round(ls.facts * 100)}% accuracy)`, severity: "bad" });
                    }
                    if (ls.sentiment_consistency != null && ls.sentiment_consistency < 0.6) {
                      issues.push({ label: "Sentiment flip", detail: "Agent tone shifted abruptly (e.g. positive to negative)", severity: "warn" });
                    }
                    if (ls.outcome_evidence != null && ls.outcome_evidence === 0) {
                      issues.push({ label: "No outcome evidence", detail: "Call outcome recorded but transcript doesn't support it", severity: "info" });
                    }
                    if (selectedRun.outcome === "escalated" && !selectedRun.escalation_signal) {
                      issues.push({ label: "Unexpected escalation", detail: "Call was escalated but no escalation signal was detected in transcript", severity: "info" });
                    }

                    if (issues.length === 0) return null;

                    return (
                      <div style={{ marginTop: 16 }}>
                        <div className="section-title" style={{ marginBottom: 8 }}>Issues Found ({issues.length})</div>
                        <div className="report-issues">
                          {issues.map((issue, i) => (
                            <div key={i} className={`report-issue report-issue-${issue.severity}`}>
                              <div className="report-issue-label">{issue.label}</div>
                              <div className="report-issue-detail">{issue.detail}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })()}

                  {/* What went well */}
                  {(() => {
                    const good: string[] = [];
                    const ls = selectedRun.layer_scores || {};

                    if (ls.schema != null && ls.schema >= 0.9) good.push("Response schema valid");
                    if (ls.citations != null && ls.citations >= 0.8) good.push("Claims backed by evidence");
                    if (ls.facts != null && ls.facts >= 0.8) good.push("Facts accurate");
                    if (ls.sentiment_consistency != null && ls.sentiment_consistency >= 0.8) good.push("Consistent tone");
                    if (!selectedRun.hallucination_detected) good.push("No hallucinations");
                    if (!selectedRun.escalation_signal) good.push("No escalation needed");

                    if (good.length === 0) return null;

                    return (
                      <div style={{ marginTop: 16 }}>
                        <div className="section-title" style={{ marginBottom: 8 }}>Passed Checks</div>
                        <div className="report-passed">
                          {good.map((item, i) => (
                            <span key={i} className="badge badge-pass" style={{ margin: "0 4px 4px 0" }}>{item}</span>
                          ))}
                        </div>
                      </div>
                    );
                  })()}
                </>
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
