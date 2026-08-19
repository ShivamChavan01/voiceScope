"use client";

import { useState, useEffect, useMemo } from "react";
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
  getKnowledge,
  createKnowledge,
  deleteKnowledge,
  type Alert,
  type ExtractionSchema,
  type QACohort,
  type KnowledgeEntry,
} from "@/lib/api";

const METRIC_OPTIONS = [
  { value: "hallucination_rate", label: "Hallucination Rate" },
  { value: "escalation_rate", label: "Escalation Rate" },
  { value: "avg_quality_score", label: "Avg Quality Score" },
  { value: "total_calls", label: "Total Calls" },
  { value: "negative_sentiment_rate", label: "Negative Sentiment Rate" },
];

function ProvidersTab() {
  const providers = {
    "Speech-to-Text": ["Deepgram", "Gemini", "Whisper"],
    "LLM": ["OpenAI", "Anthropic", "Gemini", "Groq", "Ollama", "Mistral"],
    "Embeddings": ["OpenAI", "Gemini"],
  };

  return (
    <div>
      <div className="settings-group" style={{ marginBottom: 16, padding: 12, borderRadius: 6, background: "var(--muted)", border: "1px solid var(--border)" }}>
        <span style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
          API keys are configured in your <code style={{ color: "var(--primary)" }}>.env</code> file on the server. See <code style={{ color: "var(--primary)" }}>.env.example</code> for all available options. Set <code style={{ color: "var(--primary)" }}>LLM_PROVIDER</code> and <code style={{ color: "var(--primary)" }}>STT_PROVIDER</code> to choose which providers to use.
        </span>
      </div>

      {Object.entries(providers).map(([category, list]) => (
        <div key={category} style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, color: "var(--muted-foreground)", marginBottom: 6 }}>{category}</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {list.map((p) => (
              <span key={p} style={{ padding: "4px 10px", borderRadius: 4, background: "var(--muted)", border: "1px solid var(--border)", fontSize: 12, color: "var(--foreground)" }}>{p}</span>
            ))}
          </div>
        </div>
      ))}
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

  // eslint-disable-next-line react-hooks/purity -- display-only relative time, frozen at mount
  const nowTs = useMemo(() => Date.now(), []);
  const relativeTime = (dateStr: string) => {
    if (!dateStr) return "—";
    const diff = nowTs - new Date(dateStr).getTime();
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

function KnowledgeTab() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", content: "" });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getKnowledge().then(setEntries).catch(() => setEntries([])).finally(() => setLoading(false));
  }, []);

  const addEntry = async () => {
    if (!form.content.trim()) return;
    setError(null);
    try {
      const res = await createKnowledge({ title: form.title, content: form.content });
      setEntries((p) => [
        {
          id: res.entry_id,
          title: form.title || "Untitled policy",
          content: form.content,
          created_at: new Date().toISOString(),
        },
        ...p,
      ]);
      setForm({ title: "", content: "" });
      setShowForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add policy");
    }
  };

  const removeEntry = async (id: number) => {
    try {
      await deleteKnowledge(id);
      setEntries((p) => p.filter((e) => e.id !== id));
    } catch (err) {
      console.error("Failed to delete policy:", err);
    }
  };

  return (
    <div>
      <div className="settings-group">
        <div className="settings-group-title">Knowledge Base</div>
        <div className="settings-group-subtitle">
          Policies the harness checks agent claims against. Entries merge with the default{" "}
          <code style={{ color: "var(--primary)" }}>knowledge/business_policy.md</code> seed.
        </div>
      </div>

      <div className="section-header" style={{ marginBottom: 16 }}>
        <div>
          <div className="section-title">Your Policies</div>
          <div className="f-hint" style={{ marginTop: 2 }}>Add, edit, or remove grounding policies</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>{showForm ? "Cancel" : "+ Add policy"}</button>
      </div>

      {showForm && (
        <div className="f-panel">
          <div className="f-grid f-grid-2">
            <div>
              <label className="f-label">Title</label>
              <input className="f-input" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="e.g. Refund Policy" />
            </div>
          </div>
          <div className="f-grid">
            <div>
              <label className="f-label">Policy Text</label>
              <textarea className="f-input" data-mono rows={6} value={form.content} onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))} placeholder="Agents cannot guarantee same-day refunds under any circumstances." style={{ resize: "vertical", minHeight: 120 }} />
            </div>
          </div>
          {error && <div className="f-hint" style={{ color: "var(--destructive)", marginBottom: 12 }}>{error}</div>}
          <button className="btn btn-primary" onClick={addEntry}>Add Policy</button>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead><tr><th>Title</th><th>Policy</th><th>Added</th><th></th></tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>Loading...</td></tr>
            ) : entries.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: "center", padding: "32px 0", color: "var(--muted-foreground)" }}>
                No custom policies yet. The default policy file is active. Add your own policies above.
              </td></tr>
            ) : (
              entries.map((e) => (
                <tr key={e.id}>
                  <td className="text-primary" style={{ fontWeight: 500 }}>{e.title}</td>
                  <td className="text-secondary" style={{ whiteSpace: "normal", minWidth: 280, lineHeight: 1.4 }}>{e.content}</td>
                  <td className="mono text-muted">{new Date(e.created_at).toLocaleDateString()}</td>
                  <td>
                    <button onClick={() => removeEntry(e.id)} style={{ background: "none", border: "none", color: "var(--muted-foreground)", cursor: "pointer", fontSize: 14, padding: "2px 6px" }} title="Delete">×</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="f-api-hint">
        <strong style={{ color: "var(--primary)" }}>API:</strong>{" "}
        <span className="mono" style={{ fontSize: 11 }}>GET /knowledge</span> list ·{" "}
        <span className="mono" style={{ fontSize: 11 }}>POST /knowledge</span> add ·{" "}
        <span className="mono" style={{ fontSize: 11 }}>DELETE /knowledge/:id</span> remove
      </div>
    </div>
  );
}

function IntegrationsTab() {
  const [copied, setCopied] = useState(false);
  const backendUrl = typeof window !== "undefined" ? window.location.origin : "";
  const webhookUrl = `${backendUrl}/api/v1/webhooks/call-completed`;

  const copyUrl = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      <div className="settings-group">
        <div className="settings-group-title">Bolna AI</div>
        <div className="settings-group-subtitle">
          VoiceScope auto-parses Bolna webhooks. No code changes needed — just set the webhook URL in your Bolna agent.
        </div>

        <div className="f-panel">
          <div className="f-label">Webhook URL (copy this)</div>
          <div className="f-row" style={{ marginBottom: 16 }}>
            <input className="f-input" data-mono readOnly value={webhookUrl} style={{ flex: 1 }} />
            <button className="btn btn-primary" onClick={copyUrl} style={{ minWidth: 80 }}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>

          <div className="f-label" style={{ marginBottom: 8 }}>Setup Steps</div>
          <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "var(--secondary-foreground)", lineHeight: 1.8 }}>
            <li>Go to <span className="mono" style={{ color: "var(--primary)" }}>bolna.ai</span> → Dashboard → Your Agent</li>
            <li>Click the <strong>Tools</strong> tab or <strong>Settings</strong></li>
            <li>Paste the Webhook URL above into the <strong>Webhook URL</strong> field</li>
            <li>Save — Bolna will POST call data here after every call</li>
          </ol>
        </div>

        <div className="f-panel" style={{ marginTop: 12 }}>
          <div className="f-label" style={{ marginBottom: 8 }}>What VoiceScope receives</div>
          <div style={{ fontSize: 12, color: "var(--secondary-foreground)", lineHeight: 1.6 }}>
            After each Bolna call, VoiceScope automatically extracts: transcript, sentiment, intent, hallucination detection, escalation signals, and a truth score. All data appears in the <strong>Runs</strong> tab.
          </div>
        </div>
      </div>

      <div className="settings-group">
        <div className="settings-group-title">Other Platforms</div>
        <div className="settings-group-subtitle">
          VoiceScope also supports Vapi, Retell, Bland, Synthflow, and Air.ai out of the box. Generic webhooks work too.
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Platform</th><th>Webhook Event</th><th>Status</th></tr></thead>
            <tbody>
              {[
                { name: "Bolna", event: "call.completed", status: "Supported" },
                { name: "Vapi", event: "end-of-call-report", status: "Supported" },
                { name: "Retell", event: "call_analyzed", status: "Supported" },
                { name: "Bland", event: "call_ended", status: "Supported" },
                { name: "Synthflow", event: "call finished", status: "Supported" },
                { name: "Air.ai", event: "POST_CALL_DATA", status: "Supported" },
                { name: "Generic", event: "Any JSON payload", status: "Supported" },
              ].map((p) => (
                <tr key={p.name}>
                  <td className="text-primary">{p.name}</td>
                  <td className="mono text-secondary">{p.event}</td>
                  <td><span className="badge badge-pass">{p.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [tab, setTab] = useState("integrations");

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Configure providers, guardrails, alerts, and integrations</p>
      </div>

      <div className="settings-tabs">
        {(["integrations", "providers", "guardrails", "alerts", "schemas", "cohorts", "knowledge"] as const).map((t) => (
          <button key={t} className={`settings-tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "integrations" && <IntegrationsTab />}
      {tab === "providers" && <ProvidersTab />}
      {tab === "guardrails" && <GuardrailsTab />}
      {tab === "alerts" && <AlertsTab />}
      {tab === "schemas" && <SchemasTab />}
      {tab === "cohorts" && <CohortsTab />}
      {tab === "knowledge" && <KnowledgeTab />}
    </>
  );
}
