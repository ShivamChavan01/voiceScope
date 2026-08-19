"use client";

import { useState, useEffect } from "react";
import {
  getBenchmark,
  getWeights,
  getLoopStatus,
  runLoop,
  type BenchmarkSummary,
} from "@/lib/api";

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="hero-cell" style={{ padding: "16px 20px" }}>
      <div className="hero-cell-label">{label}</div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 26, fontWeight: 700, color: color || "var(--foreground)", letterSpacing: "-0.03em", lineHeight: 1.2 }}>
        {value}
      </div>
      {sub && <div className="hero-cell-sub" style={{ marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

function pct(x: number) {
  return `${(x * 100).toFixed(0)}%`;
}

function scoreColor(x: number) {
  if (x >= 0.8) return "var(--success)";
  if (x >= 0.5) return "var(--warning)";
  return "var(--destructive)";
}

const ACCURACY_ROWS: { key: keyof BenchmarkSummary; label: string }[] = [
  { key: "sentiment_accuracy", label: "Sentiment" },
  { key: "outcome_accuracy", label: "Outcome" },
  { key: "hallucination_accuracy", label: "Hallucination" },
  { key: "escalation_accuracy", label: "Escalation" },
  { key: "avg_citation_coverage", label: "Citation coverage" },
  { key: "avg_fact_accuracy", label: "Fact accuracy" },
];

export default function BenchmarkPage() {
  const [benchmark, setBenchmark] = useState<BenchmarkSummary | null>(null);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [weightHistory, setWeightHistory] = useState(0);
  const [suggestions, setSuggestions] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([
      getBenchmark().catch(() => null),
      getWeights().catch(() => ({ weights: {}, history: 0 })),
      getLoopStatus().catch(() => ({ optimizer_weights: {}, optimization_history: 0, prompt_stats: [], suggestions: [] })),
    ]).then(([bench, w, status]) => {
      if (!active) return;
      if (bench) setBenchmark(bench);
      setWeights(w.weights || {});
      setWeightHistory(w.history || 0);
      setSuggestions(status.suggestions || []);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [reloadKey]);

  const handleRunLoop = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await runLoop();
      setBenchmark(res.benchmark);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run improvement loop");
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <div className="page-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div>
          <h1 className="page-title">Harness Benchmark</h1>
          <p className="page-subtitle">Measure hallucination-detection accuracy on labeled calls, then tune the layer weights</p>
        </div>
        <button className="btn btn-primary" onClick={handleRunLoop} disabled={running || loading}>
          {running ? "Running..." : "Run improvement loop"}
        </button>
      </div>

      {error && (
        <div className="f-api-hint" style={{ marginBottom: 16, borderColor: "rgba(192,80,77,0.2)", color: "var(--destructive)" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="empty-state">Loading benchmark...</div>
      ) : !benchmark ? (
        <div className="empty-state">
          Benchmark data unavailable. Make sure <code>tests/test_data_labeled.json</code> exists.
        </div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
            <StatCard label="Avg Truth Score" value={benchmark.avg_truth_score.toFixed(2)} color="var(--primary)" sub={`${benchmark.total_tests} labeled calls`} />
            <StatCard label="Sentiment Accuracy" value={pct(benchmark.sentiment_accuracy)} color={scoreColor(benchmark.sentiment_accuracy)} />
            <StatCard label="Outcome Accuracy" value={pct(benchmark.outcome_accuracy)} color={scoreColor(benchmark.outcome_accuracy)} />
            <StatCard label="Hallucination Accuracy" value={pct(benchmark.hallucination_accuracy)} color={scoreColor(benchmark.hallucination_accuracy)} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
            <div className="hero-cell" style={{ padding: "16px 20px" }}>
              <div className="hero-cell-label">Per-Layer Accuracy</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
                {ACCURACY_ROWS.map((row) => {
                  const v = benchmark[row.key] as number;
                  return (
                    <div key={row.key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 12, color: "var(--secondary-foreground)", minWidth: 120 }}>{row.label}</span>
                      <div style={{ flex: 1, height: 6, background: "#232328", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ width: `${Math.round(v * 100)}%`, height: "100%", background: scoreColor(v), borderRadius: 3 }} />
                      </div>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: scoreColor(v), minWidth: 36, textAlign: "right" }}>{pct(v)}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="hero-cell" style={{ padding: "16px 20px" }}>
              <div className="hero-cell-label">Layer Weights</div>
              <div className="f-hint" style={{ marginBottom: 12 }}>Auto-tuned by the optimizer · {weightHistory} optimization rounds</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {Object.entries(weights).map(([layer, w]) => (
                  <div key={layer} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 12, color: "var(--secondary-foreground)", minWidth: 120, fontFamily: "var(--font-mono)" }}>{layer}</span>
                    <div style={{ flex: 1, height: 6, background: "#232328", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ width: `${(w * 100).toFixed(0)}%`, height: "100%", background: "var(--primary)", borderRadius: 3 }} />
                    </div>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--foreground)", minWidth: 36, textAlign: "right" }}>{w.toFixed(2)}</span>
                  </div>
                ))}
                {Object.keys(weights).length === 0 && (
                  <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>Run the improvement loop to tune weights.</span>
                )}
              </div>
            </div>
          </div>

          <div className="section-header">
            <div className="section-title">Weakest & Strongest Layers</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
            <div className="hero-cell" style={{ padding: "16px 20px", borderColor: "rgba(192,80,77,0.2)" }}>
              <div className="hero-cell-label">Weakest Layer</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 16, color: "var(--destructive)" }}>{benchmark.weakest_layer}</div>
            </div>
            <div className="hero-cell" style={{ padding: "16px 20px", borderColor: "rgba(58,158,111,0.2)" }}>
              <div className="hero-cell-label">Strongest Layer</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 16, color: "var(--success)" }}>{benchmark.strongest_layer}</div>
            </div>
          </div>

          <div className="section-header">
            <div className="section-title">Improvement Suggestions</div>
          </div>
          {suggestions.length === 0 ? (
            <div className="empty-state">Run the improvement loop to generate prompt suggestions.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {suggestions.map((s, i) => (
                <div key={i} className="report-issue report-issue-info">
                  <div className="report-issue-detail" style={{ fontFamily: "var(--font-sans)" }}>
                    {typeof s === "string" ? s : JSON.stringify(s)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
