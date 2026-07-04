"use client";

import { useEffect, useState } from "react";
import { HarnessBar } from "@/components/harness-bar";
import { TrendChart } from "@/components/trend-chart";
import {
  getRuns,
  getIncidents,
  getMetrics,
  type Run,
  type AlertIncident,
  type MetricsSummary,
} from "@/lib/api";

function AlertIcon({ color }: { color: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width={16} height={16} style={{ flexShrink: 0 }}>
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

function formatDuration(seconds: number | null) {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function OverviewPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [incidents, setIncidents] = useState<AlertIncident[]>([]);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getRuns({ limit: 5 }).catch(() => ({ runs: [], total: 0, limit: 5, offset: 0 })),
      getIncidents(10).catch(() => []),
      getMetrics(1440).catch(() => null),
    ]).then(([runsRes, inc, met]) => {
      setRuns(runsRes.runs);
      setIncidents(inc);
      setMetrics(met);
      setLoading(false);
    });
  }, []);

  const truthScore = metrics?.avg_quality_score ?? 0;
  const totalCalls = metrics?.total_calls ?? 0;

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
      {/* Hero Row */}
      <div className="hero-row">
        <div className="hero-cell">
          <div className="hero-cell-label">Truth Score</div>
          <div className="hero-cell-value accent">{truthScore.toFixed(2)}</div>
          <div className="hero-cell-sub">last 24h avg · {totalCalls} calls</div>
          <TrendChart />
        </div>
        <div className="hero-cell">
          <div className="hero-cell-label">Harness Integrity</div>
          <HarnessBar scores={[92,88,91,97,83,92,96,89,94,90,87,93,91]} />
        </div>
      </div>

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
                <span className="alert-text">{inc.message}</span>
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
                <th>Sentiment</th>
                <th>Duration</th>
                <th>Score</th>
                <th>Status</th>
                <th>Provider</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>
                    No runs yet. Analyze an audio file to get started.
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr key={run.run_id}>
                    <td><span className="mono text-accent">{run.run_id.slice(0, 12)}</span></td>
                    <td><span className="text-secondary">{run.intent || "—"}</span></td>
                    <td><span className="text-secondary">{run.sentiment || "—"}</span></td>
                    <td><span className="mono text-secondary">{formatDuration(run.duration_seconds)}</span></td>
                    <td>
                      <span className={`mono ${run.truth_score != null ? scoreColor(run.truth_score) : "text-muted"}`}>
                        {run.truth_score != null ? run.truth_score.toFixed(2) : "—"}
                      </span>
                    </td>
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
    </>
  );
}
