"use client";

import { useState, useRef, useEffect } from "react";
import {
  getAlerts,
  createAlertRule,
  deleteAlertRule,
  getSchemas,
  createSchema,
  deleteSchema,
  getQACohorts,
  createQACohort,
  getGuardrailStatus,
  type Alert,
  type ExtractionSchema,
  type QACohort,
} from "@/lib/api";

const ALL_PROVIDERS = ["OpenAI", "Deepgram", "Google", "Anthropic", "Azure", "AWS Bedrock", "Whisper", "Assembly AI", "Eleven Labs", "Cohere", "Mistral", "Meta"];

const METRIC_OPTIONS = [
  { value: "hallucination_rate", label: "Hallucination Rate" },
  { value: "escalation_rate", label: "Escalation Rate" },
  { value: "avg_quality_score", label: "Avg Quality Score" },
  { value: "total_calls", label: "Total Calls" },
  { value: "negative_sentiment_rate", label: "Negative Sentiment Rate" },
];

function MultiSelect({ label, selected, onToggle }: { label: string; selected: string[]; onToggle: (p: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <div className="settings-group">
      <div className="settings-group-title">{label}</div>
      <div className="settings-row">
        <span className="settings-row-label">Providers</span>
        <div ref={ref} style={{ position: "relative", minWidth: 200 }}>
          <button className="f-input f-row" style={{ cursor: "pointer", textAlign: "left" }} onClick={() => setOpen(!open)}>
            <span className={`f-row-grow ${selected.length === 0 ? "f-hint" : ""}`} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {selected.length === 0 ? "Select providers..." : selected.join(", ")}
            </span>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ flexShrink: 0 }}><path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
          {open && (
            <div style={{ position: "absolute", top: "100%", left: 0, right: 0, marginTop: 4, background: "var(--popover)", border: "1px solid rgba(255,255,255,0.14)", borderRadius: "var(--radius)", padding: 4, zIndex: 100, maxHeight: 240, overflowY: "auto" }}>
              {ALL_PROVIDERS.map((p) => (
                <button key={p} onClick={() => onToggle(p)} className="f-row" style={{ width: "100%", padding: "6px 8px", background: selected.includes(p) ? "rgba(79,195,247,0.12)" : "transparent", border: "none", borderRadius: 4, color: selected.includes(p) ? "var(--primary)" : "var(--foreground)", fontSize: 13, cursor: "pointer", textAlign: "left" }}>
                  <span style={{ width: 14, height: 14, border: `1.5px solid ${selected.includes(p) ? "var(--primary)" : "var(--muted-foreground)"}`, borderRadius: 3, display: "grid", placeItems: "center", background: selected.includes(p) ? "var(--primary)" : "transparent", flexShrink: 0 }}>
                    {selected.includes(p) && <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5L4.5 7.5L8 3" stroke="var(--background)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>}
                  </span>
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProviderKeyRow({ name }: { name: string }) {
  const [show, setShow] = useState(false);
  const [val, setVal] = useState("");
  return (
    <div className="settings-row">
      <span className="settings-row-label" style={{ color: "var(--primary)" }}>{name}</span>
      <div style={{ position: "relative", minWidth: 200 }}>
        <input className="f-input" data-mono type={show ? "text" : "password"} value={val} onChange={(e) => setVal(e.target.value)} placeholder={`Enter ${name} API key`} style={{ paddingRight: 32 }} />
        <button onClick={() => setShow(!show)} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", padding: 0, color: "var(--muted-foreground)", display: "grid", placeItems: "center" }} title={show ? "Hide" : "Show"}>
          {show
            ? <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M1 7s2.5-4 6-4 6 4 6 4-2.5 4-6 4-6-4-6-4z" /><circle cx="7" cy="7" r="2" /></svg>
            : <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M1.5 1.5l11 11M5.5 5.5a2 2 0 002.8 2.8M1 7s2.5-4 6-4a5.8 5.8 0 012.5.6M13 7s-1.2 2-3.5 3" /></svg>
          }
        </button>
      </div>
    </div>
  );
}

function ProvidersTab() {
  const [stt, setStt] = useState(["Deepgram"]);
  const [llm, setLlm] = useState(["OpenAI"]);
  const [embed, setEmbed] = useState(["OpenAI"]);

  const toggle = (setter: React.Dispatch<React.SetStateAction<string[]>>, list: string[], p: string) => {
    setter(list.includes(p) ? list.filter((x) => x !== p) : [...list, p]);
  };

  return (
    <div>
      <MultiSelect label="Speech-to-Text" selected={stt} onToggle={(p) => toggle(setStt, stt, p)} />
      {stt.map((p) => <ProviderKeyRow key={p} name={p} />)}

      <MultiSelect label="LLM" selected={llm} onToggle={(p) => toggle(setLlm, llm, p)} />
      {llm.map((p) => <ProviderKeyRow key={p} name={p} />)}

      <MultiSelect label="Embeddings" selected={embed} onToggle={(p) => toggle(setEmbed, embed, p)} />
      {embed.map((p) => <ProviderKeyRow key={p} name={p} />)}
    </div>
  );
}

function GuardrailsTab() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    getGuardrailStatus().then(setStatus).catch(() => {});
  }, []);

  const categories = status?.categories ?? ["self_harm", "violence", "harassment", "medical_advice", "financial_advice"];
  const pii = status?.pii_patterns ?? ["Email", "Phone", "SSN", "Credit card", "IP address"];

  return (
    <div>
      <div className="f-hint" style={{ marginBottom: 20, lineHeight: 1.6 }}>Content guardrails are system-wide and managed server-side. Changes require a backend restart.</div>

      <div className="settings-group">
        <div className="settings-group-title">Content Categories</div>
        <div className="settings-group-subtitle">Regex-based harmful content detection — input and output</div>
        {(Array.isArray(categories) ? categories : Object.keys(categories)).map((c: string) => (
          <div className="settings-row" key={c}><span className="settings-row-label">{c.replace(/_/g, " ")}</span><span className="badge badge-pass">Active</span></div>
        ))}
      </div>

      <div className="settings-group">
        <div className="settings-group-title">PII Redaction</div>
        <div className="settings-group-subtitle">Automatically redacts personally identifiable information</div>
        {(Array.isArray(pii) ? pii : Object.keys(pii)).map((p: string) => (
          <div className="settings-row" key={p}><span className="settings-row-label">{p}</span><span className="badge badge-pass">Active</span></div>
        ))}
      </div>

      <div className="settings-group">
        <div className="settings-group-title">Endpoints</div>
        <div className="settings-row"><span className="settings-row-label mono" style={{ fontSize: 12 }}>POST /api/v1/guardrails/check</span><span className="f-hint">Available</span></div>
        <div className="settings-row"><span className="settings-row-label mono" style={{ fontSize: 12 }}>GET /api/v1/guardrails/status</span><span className="f-hint">Available</span></div>
      </div>
    </div>
  );
}

function AlertsTab() {
  const [rules, setRules] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", metric: "avg_quality_score", comparator: "<", threshold: "", window: "60", webhook: "", email: "" });

  useEffect(() => {
    getAlerts().then(setRules).catch(() => setRules([])).finally(() => setLoading(false));
  }, []);

  const addRule = async () => {
    if (!form.name || !form.threshold) return;
    try {
      const res = await createAlertRule({
        name: form.name,
        metric: form.metric,
        comparator: form.comparator,
        threshold: parseFloat(form.threshold),
        window_minutes: parseInt(form.window) || 60,
        notify_url: form.webhook || undefined,
        notify_email: form.email || undefined,
      });
      setRules((p) => [...p, {
        id: res.rule_id,
        name: form.name,
        metric: form.metric,
        comparator: form.comparator,
        threshold: parseFloat(form.threshold),
        window_minutes: parseInt(form.window) || 60,
        enabled: 1,
        last_triggered: null,
        notify_url: form.webhook || null,
        notify_email: form.email || null,
        created_at: new Date().toISOString(),
      }]);
      setForm({ name: "", metric: "avg_quality_score", comparator: "<", threshold: "", window: "60", webhook: "", email: "" });
      setShowForm(false);
    } catch (err) {
      console.error("Failed to create rule:", err);
    }
  };

  const removeRule = async (id: number) => {
    try {
      await deleteAlertRule(id);
      setRules((p) => p.filter((r) => r.id !== id));
    } catch (err) {
      console.error("Failed to delete rule:", err);
    }
  };

  return (
    <div>
      <div className="section-header" style={{ marginBottom: 16 }}>
        <div>
          <div className="section-title">Alert Rules</div>
          <div className="f-hint" style={{ marginTop: 2 }}>Threshold-based rules that fire incidents when metrics breach limits</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>{showForm ? "Cancel" : "+ New rule"}</button>
      </div>

      {showForm && (
        <div className="f-panel">
          <div className="f-grid f-grid-2">
            <div><label className="f-label">Rule Name</label><input className="f-input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Low Quality Score" /></div>
            <div><label className="f-label">Metric</label><select className="f-select" value={form.metric} onChange={(e) => setForm((f) => ({ ...f, metric: e.target.value }))}>{METRIC_OPTIONS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}</select></div>
          </div>
          <div className="f-grid f-grid-3">
            <div><label className="f-label">Comparator</label><select className="f-select" value={form.comparator} onChange={(e) => setForm((f) => ({ ...f, comparator: e.target.value }))}>{[">", "<", ">=", "<=", "=="].map((c) => <option key={c}>{c}</option>)}</select></div>
            <div><label className="f-label">Threshold</label><input className="f-input" data-mono type="number" step="0.01" value={form.threshold} onChange={(e) => setForm((f) => ({ ...f, threshold: e.target.value }))} placeholder="0.70" /></div>
            <div><label className="f-label">Window (min)</label><input className="f-input" data-mono type="number" value={form.window} onChange={(e) => setForm((f) => ({ ...f, window: e.target.value }))} /></div>
          </div>
          <div className="f-grid f-grid-2">
            <div><label className="f-label">Webhook URL <span className="f-hint">(optional)</span></label><input className="f-input" data-mono value={form.webhook} onChange={(e) => setForm((f) => ({ ...f, webhook: e.target.value }))} placeholder="https://hooks.example.com/alert" /></div>
            <div><label className="f-label">Email <span className="f-hint">(optional)</span></label><input className="f-input" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} placeholder="ops@example.com" /></div>
          </div>
          <button className="btn btn-primary" onClick={addRule}>Create Rule</button>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead><tr><th>Rule</th><th>Metric</th><th>Condition</th><th>Window</th><th>Last Triggered</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>Loading...</td></tr>
            ) : rules.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>No alert rules configured</td></tr>
            ) : (
              rules.map((rule) => (
                <tr key={rule.id}>
                  <td><span className="text-primary" style={{ fontSize: 13 }}>{rule.name}</span></td>
                  <td><span className="mono text-secondary">{METRIC_OPTIONS.find((m) => m.value === rule.metric)?.label || rule.metric}</span></td>
                  <td><span className="mono text-primary">{rule.comparator} {rule.threshold}</span></td>
                  <td><span className="mono text-muted">{rule.window_minutes}m</span></td>
                  <td><span className="mono text-muted">{rule.last_triggered ? new Date(rule.last_triggered).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</span></td>
                  <td><span className={`badge ${rule.enabled ? "badge-pass" : "badge-flag"}`}>{rule.enabled ? "Enabled" : "Disabled"}</span></td>
                  <td>
                    <button onClick={() => removeRule(rule.id)} style={{ background: "none", border: "none", color: "var(--muted-foreground)", cursor: "pointer", fontSize: 14, padding: "2px 6px" }} title="Delete">×</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="f-api-hint">
        <strong style={{ color: "var(--primary)" }}>API:</strong>{" "}
        <span className="mono" style={{ fontSize: 11 }}>GET /monitoring/alerts</span> list ·{" "}
        <span className="mono" style={{ fontSize: 11 }}>POST /monitoring/alerts</span> create ·{" "}
        <span className="mono" style={{ fontSize: 11 }}>DELETE /monitoring/alerts/:id</span> remove ·{" "}
        <span className="mono" style={{ fontSize: 11 }}>POST /monitoring/check</span> evaluate
      </div>
    </div>
  );
}

function SchemasTab() {
  const [schemas, setSchemas] = useState<ExtractionSchema[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "" });

  useEffect(() => {
    getSchemas().then(setSchemas).catch(() => setSchemas([])).finally(() => setLoading(false));
  }, []);

  const addSchema = async () => {
    if (!form.name) return;
    try {
      const res = await createSchema({ name: form.name, description: form.description, fields: [] });
      setSchemas((p) => [...p, { id: res.schema_id, name: form.name, description: form.description, fields: [], created_at: new Date().toISOString() }]);
      setForm({ name: "", description: "" });
      setShowForm(false);
    } catch (err) {
      console.error("Failed to create schema:", err);
    }
  };

  const removeSchema = async (id: number) => {
    try {
      await deleteSchema(id);
      setSchemas((p) => p.filter((s) => s.id !== id));
    } catch (err) {
      console.error("Failed to delete schema:", err);
    }
  };

  const relativeTime = (dateStr: string) => {
    if (!dateStr) return "—";
    const diff = Date.now() - new Date(dateStr).getTime();
    const days = Math.floor(diff / 86400000);
    if (days < 1) return "today";
    if (days === 1) return "1d ago";
    if (days < 7) return `${days}d ago`;
    return `${Math.floor(days / 7)}w ago`;
  };

  return (
    <div>
      <div className="section-header" style={{ marginBottom: 16 }}>
        <div className="section-title">Extraction Schemas</div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>{showForm ? "Cancel" : "+ Add schema"}</button>
      </div>

      {showForm && (
        <div className="f-panel">
          <div className="f-grid f-grid-2">
            <div><label className="f-label">Schema Name</label><input className="f-input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. order_lookup" /></div>
            <div><label className="f-label">Description</label><input className="f-input" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Optional description" /></div>
          </div>
          <button className="btn btn-primary" onClick={addSchema}>Create Schema</button>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead><tr><th>Schema</th><th>Fields</th><th>Updated</th><th></th></tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>Loading...</td></tr>
            ) : schemas.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>No schemas configured</td></tr>
            ) : (
              schemas.map((s) => (
                <tr key={s.id}>
                  <td className="mono text-accent">{s.name}</td>
                  <td className="text-secondary">{s.fields.map((f) => f.name).join(", ") || "No fields"}</td>
                  <td className="mono text-muted">{relativeTime(s.created_at)}</td>
                  <td>
                    <button onClick={() => removeSchema(s.id)} style={{ background: "none", border: "none", color: "var(--muted-foreground)", cursor: "pointer", fontSize: 14, padding: "2px 6px" }} title="Delete">×</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CohortsTab() {
  const [cohorts, setCohorts] = useState<QACohort[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", sampling_pct: "10", weekly_max: "100" });

  useEffect(() => {
    getQACohorts().then(setCohorts).catch(() => setCohorts([])).finally(() => setLoading(false));
  }, []);

  const addCohort = async () => {
    if (!form.name) return;
    try {
      const res = await createQACohort({
        name: form.name,
        sampling_pct: parseFloat(form.sampling_pct) || 10,
        weekly_max: parseInt(form.weekly_max) || 100,
      });
      setCohorts((p) => [...p, {
        id: res.cohort_id,
        name: form.name,
        agent_filter: null,
        platform_filter: null,
        min_duration: null,
        max_duration: null,
        sampling_pct: parseFloat(form.sampling_pct) || 10,
        weekly_max: parseInt(form.weekly_max) || 100,
        criteria: {},
        created_at: new Date().toISOString(),
      }]);
      setForm({ name: "", sampling_pct: "10", weekly_max: "100" });
      setShowForm(false);
    } catch (err) {
      console.error("Failed to create cohort:", err);
    }
  };

  return (
    <div>
      <div className="section-header" style={{ marginBottom: 16 }}>
        <div className="section-title">QA Cohorts</div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>{showForm ? "Cancel" : "+ Add cohort"}</button>
      </div>

      {showForm && (
        <div className="f-panel">
          <div className="f-grid f-grid-2">
            <div><label className="f-label">Cohort Name</label><input className="f-input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Enterprise Onboarding" /></div>
            <div><label className="f-label">Sampling %</label><input className="f-input" data-mono type="number" value={form.sampling_pct} onChange={(e) => setForm((f) => ({ ...f, sampling_pct: e.target.value }))} /></div>
          </div>
          <div className="f-grid f-grid-2">
            <div><label className="f-label">Weekly Max</label><input className="f-input" data-mono type="number" value={form.weekly_max} onChange={(e) => setForm((f) => ({ ...f, weekly_max: e.target.value }))} /></div>
          </div>
          <button className="btn btn-primary" onClick={addCohort}>Create Cohort</button>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead><tr><th>Cohort</th><th>Sampling</th><th>Weekly Max</th><th>Created</th></tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>Loading...</td></tr>
            ) : cohorts.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>No cohorts configured</td></tr>
            ) : (
              cohorts.map((c) => (
                <tr key={c.id}>
                  <td className="text-primary">{c.name}</td>
                  <td className="mono">{c.sampling_pct}%</td>
                  <td className="mono">{c.weekly_max}</td>
                  <td className="mono text-muted">{new Date(c.created_at).toLocaleDateString()}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [tab, setTab] = useState("providers");

  return (
    <>
      <div className="settings-tabs">
        {(["providers", "guardrails", "alerts", "schemas", "cohorts"] as const).map((t) => (
          <button key={t} className={`settings-tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "providers" && <ProvidersTab />}
      {tab === "guardrails" && <GuardrailsTab />}
      {tab === "alerts" && <AlertsTab />}
      {tab === "schemas" && <SchemasTab />}
      {tab === "cohorts" && <CohortsTab />}
    </>
  );
}
