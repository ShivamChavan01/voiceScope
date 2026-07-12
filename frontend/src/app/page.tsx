"use client";

import { useEffect, useState, useMemo } from "react";
import { HarnessBar, HARNESS_KEYS } from "@/components/harness-bar";
import { TrendChart } from "@/components/trend-chart";
import {
  getRuns,
  getRun,
  getIncidents,
  getMetrics,
  getRunHistory,
  getCosts,
  type Run,
  type AlertIncident,
  type MetricsSummary,
  type CostSummary,
} from "@/lib/api";

function AlertIcon({ color }: { color: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width={16} height={16} style={{ flexShrink: 0 }} aria-hidden="true">
      <path d="M8 2L1.5 13h13L8 2zM8 7v3M8 12h.01" />
    </svg>
  );
}

function scoreColor(s: number) {
  if (s >= 0.8) return "text-success";
  if (s >= 0.5) return "text-warning";
  return "text-danger";
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

function cleanIncidentMessage(msg: string) {
  return msg.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, (m) => m.slice(0, 8));
}

function formatDuration(seconds: number | null) {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function harnessScoresForRun(run: Run): number[] {
  if (!run.layer_scores) return Array(HARNESS_KEYS.length).fill(0);
  return HARNESS_KEYS.map((k) => {
    const v = run.layer_scores?.[k];
    return v != null ? Math.round(v * 100) : 0;
  });
}

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="hero-cell" style={{ padding: "16px 20px" }}>
      <div className="hero-cell-label">{label}</div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 28, fontWeight: 700, color: color || "var(--foreground)", letterSpacing: "-0.03em", lineHeight: 1.2 }}>
        {value}
      </div>
      {sub && <div className="hero-cell-sub" style={{ marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

export default function OverviewPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [incidents, setIncidents] = useState<AlertIncident[]>([]);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [historyScores, setHistoryScores] = useState<number[]>([]);
  const [harnessScores, setHarnessScores] = useState<number[]>([]);
  const [costs, setCosts] = useState<CostSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getRuns({ limit: 5 }).catch(() => ({ runs: [], total: 0, limit: 5, offset: 0 })),
      getIncidents(10).catch(() => []),
      getMetrics(1440).catch(() => null),
      getRunHistory(12).catch(() => ({ scores: [], count: 0 })),
      getCosts().catch(() => null),
    ]).then(([runsRes, inc, met, hist, cost]) => {
      setRuns(runsRes.runs);
      setIncidents(inc);
      setMetrics(met);
      setHistoryScores(hist.scores);
      setCosts(cost);
      if (runsRes.runs.length > 0) {
        const latest = runsRes.runs[0];
        getRun(latest.run_id).then((detail) => {
          if (detail.layer_scores) {
            setHarnessScores(HARNESS_KEYS.map((k) => detail.layer_scores?.[k] != null ? Math.round(detail.layer_scores[k] * 100) : 0));
          }
        }).catch(() => {});
      }
      setLoading(false);
    });
  }, []);

  const latestRun = runs[0] ?? null;
  const latestTruthScore = latestRun?.truth_score ?? null;
  const latestDegraded = !!latestRun && (!!latestRun.hallucination_detected || !!latestRun.escalation_signal);
  const displayScore = latestTruthScore != null ? (latestDegraded ? Math.min(latestTruthScore, 0.60) : latestTruthScore) : null;
  const totalCalls = metrics?.total_calls ?? runs.length;

  const sentimentBreakdown = useMemo(() => {
    const counts: Record<string, number> = {};
    runs.forEach((r) => {
      const s = r.sentiment || "unknown";
      counts[s] = (counts[s] || 0) + 1;
    });
    return counts;
  }, [runs]);

  const providerBreakdown = useMemo(() => {
    const counts: Record<string, number> = {};
    runs.forEach((r) => {
      const p = r.provider || "unknown";
      counts[p] = (counts[p] || 0) + 1;
    });
    return counts;
  }, [runs]);

  if (loading) {
    return (
      <>
        <div className="hero-row">
          <div className="hero-cell">
            <div className="hero-cell-label">Truth Score</div>
            <div className="hero-cell-value accent">—</div>
            <div className="hero-cell-sub">loading...</div>
          </div>
          <div className="hero-cell">
            <div className="hero-cell-label">Harness Integrity</div>
            <div style={{ color: "var(--muted-foreground)", fontSize: 12 }}>loading...</div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Overview</h1>
        <p className="page-subtitle">Monitor voice AI call quality across all your agents</p>
      </div>

      {/* Stats Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        <StatCard
          label="Total Calls"
          value={String(totalCalls)}
          sub={`${historyScores.length} analyzed`}
        />
        <StatCard
          label="Hallucination Rate"
          value={metrics ? `${(metrics.hallucination_rate * 100).toFixed(0)}%` : runs.length > 0 ? `${((runs.filter((r) => r.hallucination_detected).length / runs.length) * 100).toFixed(0)}%` : "—"}
          sub={metrics ? `${Math.round(metrics.hallucination_rate * totalCalls)} flagged` : `${runs.filter((r) => r.hallucination_detected).length} flagged`}
          color="var(--destructive)"
        />
        <StatCard
          label="Escalation Rate"
          value={metrics ? `${(metrics.escalation_rate * 100).toFixed(0)}%` : runs.length > 0 ? `${((runs.filter((r) => r.escalation_signal).length / runs.length) * 100).toFixed(0)}%` : "—"}
          sub={metrics ? `${Math.round(metrics.escalation_rate * totalCalls)} escalated` : `${runs.filter((r) => r.escalation_signal).length} escalated`}
          color="var(--warning)"
        />
        <StatCard
          label="Total Cost"
          value={costs?.overall?.total_cost != null ? `$${costs.overall.total_cost.toFixed(4)}` : "$0.00"}
          sub={costs?.overall?.total_input != null ? `${((costs.overall.total_input + (costs.overall.total_output ?? 0)) / 1000).toFixed(1)}K tokens` : "0 tokens"}
          color="var(--primary)"
        />
      </div>

      {/* Token Usage Breakdown */}
      {costs && (costs.overall.total_input ?? 0) > 0 && (
        <div className="hero-cell" style={{ padding: "16px 20px", marginBottom: 20 }}>
          <div className="hero-cell-label">Token Usage</div>
          <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
            <div>
              <div style={{ fontSize: 11, color: "var(--muted-foreground)", marginBottom: 4 }}>Input Tokens</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 20, fontWeight: 600, color: "var(--primary)" }}>
                {costs.overall.total_input != null ? costs.overall.total_input.toLocaleString() : "0"}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: "var(--muted-foreground)", marginBottom: 4 }}>Output Tokens</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 20, fontWeight: 600, color: "var(--success)" }}>
                {costs.overall.total_output != null ? costs.overall.total_output.toLocaleString() : "0"}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: "var(--muted-foreground)", marginBottom: 4 }}>Total</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 20, fontWeight: 600 }}>
                {costs.overall.total_input != null ? ((costs.overall.total_input + (costs.overall.total_output ?? 0))).toLocaleString() : "0"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Hero Row */}
      <div className="hero-row">
        <div className="hero-cell">
          <div className="hero-cell-label">Truth Score</div>
          <div className="hero-cell-value accent">
            {displayScore != null ? `${(displayScore * 100).toFixed(1)}%` : "—"}
            {latestDegraded && (
              <span className="badge badge-fail" style={{ marginLeft: 8, fontSize: 10, verticalAlign: "middle" }}>
                {latestRun.hallucination_detected ? "HALLUCINATION" : "ESCALATED"}
              </span>
            )}
          </div>
          <div className="hero-cell-sub">
            latest run · {totalCalls} calls analyzed
            {latestDegraded && <span style={{ color: "var(--warning)", marginLeft: 4 }}>· score capped</span>}
          </div>
          <TrendChart points={historyScores} />
        </div>
        <div className="hero-cell" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div className="hero-cell-label">Harness Integrity</div>
            <div style={{ color: "var(--muted-foreground)", fontSize: 12, marginBottom: 16 }}>
              7 validation layers scoring 0–100%
            </div>
          </div>
          <HarnessBar scores={harnessScores.length > 0 ? harnessScores : Array(HARNESS_KEYS.length).fill(0)} />
        </div>
      </div>

      {/* Sentiment + Provider Row */}
      {runs.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
          {/* Sentiment Distribution */}
          <div className="hero-cell" style={{ padding: "16px 20px" }}>
            <div className="hero-cell-label">Sentiment Distribution</div>
            <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
              {Object.entries(sentimentBreakdown).map(([sentiment, count]) => {
                const colors: Record<string, string> = { positive: "var(--success)", neutral: "var(--muted-foreground)", negative: "var(--destructive)" };
                const pct = Math.round((count / runs.length) * 100);
                return (
                  <div key={sentiment} style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ fontSize: 12, color: "var(--secondary-foreground)", textTransform: "capitalize" }}>{sentiment}</span>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: colors[sentiment] || "var(--muted-foreground)" }}>{pct}%</span>
                    </div>
                    <div style={{ height: 6, background: "#232328", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: colors[sentiment] || "var(--muted-foreground)", borderRadius: 3, transition: "width 300ms ease-out" }} />
                    </div>
                  </div>
                );
              })}
              {Object.keys(sentimentBreakdown).length === 0 && (
                <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>No data yet</span>
              )}
            </div>
          </div>

          {/* Provider Usage */}
          <div className="hero-cell" style={{ padding: "16px 20px" }}>
            <div className="hero-cell-label">Provider Usage</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
              {costs && Object.keys(costs.by_provider).length > 0 ? (
                Object.entries(costs.by_provider).map(([provider, data]) => {
                  const pct = Math.round((data.calls / Math.max(costs.overall.total_calls ?? 1, 1)) * 100);
                  const tokens = (data.input_tokens ?? 0) + (data.output_tokens ?? 0);
                  return (
                    <div key={provider} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span style={{ fontSize: 12, color: "var(--secondary-foreground)", minWidth: 70, textTransform: "capitalize" }}>{provider}</span>
                        <div style={{ flex: 1, height: 6, background: "#232328", borderRadius: 3, overflow: "hidden" }}>
                          <div style={{ width: `${pct}%`, height: "100%", background: "var(--primary)", borderRadius: 3, transition: "width 300ms ease-out" }} />
                        </div>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", minWidth: 50, textAlign: "right" }}>{data.calls} calls</span>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", minWidth: 70, textAlign: "right" }}>{tokens.toLocaleString()} tok</span>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: data.cost > 0 ? "var(--warning)" : "var(--muted-foreground)", minWidth: 60, textAlign: "right" }}>
                          {data.cost > 0 ? `$${data.cost.toFixed(4)}` : "free"}
                        </span>
                      </div>
                    </div>
                  );
                })
              ) : Object.keys(providerBreakdown).length > 0 ? (
                Object.entries(providerBreakdown).map(([provider, count]) => {
                  const pct = Math.round((count / runs.length) * 100);
                  return (
                    <div key={provider} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 12, color: "var(--secondary-foreground)", minWidth: 70, textTransform: "capitalize" }}>{provider}</span>
                      <div style={{ flex: 1, height: 6, background: "#232328", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ width: `${pct}%`, height: "100%", background: "var(--primary)", borderRadius: 3, transition: "width 300ms ease-out" }} />
                      </div>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", minWidth: 50, textAlign: "right" }}>{count} calls</span>
                    </div>
                  );
                })
              ) : (
                <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>No data yet</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Active Incidents */}
      <div className="section-header">
        <div className="section-title">Active Incidents</div>
      </div>
      <div style={{ marginBottom: 32 }}>
        {incidents.length === 0 ? (
          <div style={{ color: "var(--muted-foreground)", fontSize: 13, padding: "16px 0" }}>
            No active incidents
          </div>
        ) : (
          incidents.slice(0, 5).map((inc) => (
            <div className="alert-row" key={inc.id}>
              <AlertIcon color={inc.status === "active" ? "var(--destructive)" : "var(--warning)"} />
              <div style={{ flex: 1 }}>
                <span className="alert-text">{cleanIncidentMessage(inc.message)}</span>
                <div className="alert-time" style={{ marginTop: 2 }}>
                  {inc.rule_name} · {relativeTime(inc.triggered_at)}
                </div>
              </div>
              <span className={`badge ${inc.status === "active" ? "badge-fail" : "badge-flag"}`}>
                {inc.status}
              </span>
            </div>
          ))
        )}
      </div>

      {/* Recent Runs */}
      <div className="section-header">
        <div className="section-title">Recent Runs</div>
        <a href="/runs" className="btn btn-ghost">View all →</a>
      </div>
      <div className="table-wrap">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Intent</th>
                <th>Hallucination</th>
                <th>Score</th>
                <th>Harness</th>
                <th>Duration</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "48px 24px" }}>
                    <div style={{ color: "var(--muted-foreground)", fontSize: 13, marginBottom: 16 }}>
                      No calls analyzed yet. Upload your first audio file to see insights here.
                    </div>
                    <a href="/runs" className="btn btn-primary">
                      Analyze a call →
                    </a>
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr key={run.run_id} onClick={() => window.location.href = "/runs"} style={{ cursor: "pointer" }}>
                    <td><span className="mono text-accent">{run.run_id.slice(0, 12)}</span></td>
                    <td><span className="text-secondary">{run.intent || "—"}</span></td>
                    <td>
                      <span className={`badge ${run.hallucination_detected ? "badge-fail" : "badge-pass"}`}>
                        {run.hallucination_detected ? "Detected" : "Clean"}
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
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
