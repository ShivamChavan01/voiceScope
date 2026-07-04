const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────

export interface Run {
  run_id: string;
  intent: string | null;
  sentiment: string | null;
  outcome: string | null;
  hallucination_detected: number;
  escalation_signal: number;
  truth_score: number | null;
  confidence: string | null;
  quality_score: number | null;
  cost_usd: number | null;
  provider: string | null;
  model: string | null;
  duration_seconds: number | null;
  word_count: number | null;
  status: string;
  transcript_preview: string | null;
  created_at: string;
}

export interface RunsResponse {
  runs: Run[];
  total: number;
  limit: number;
  offset: number;
}

export interface Alert {
  id: number;
  name: string;
  metric: string;
  comparator: string;
  threshold: number;
  window_minutes: number;
  enabled: number;
  last_triggered: string | null;
  notify_url: string | null;
  notify_email: string | null;
  created_at: string;
}

export interface AlertIncident {
  id: number;
  rule_id: number;
  rule_name: string;
  metric: string;
  metric_value: number;
  message: string;
  status: string;
  triggered_at: string;
}

export interface MetricsSummary {
  window_minutes: number;
  total_calls: number;
  avg_quality_score: number | null;
  avg_cost_usd: number | null;
  total_cost_usd: number;
  hallucination_rate: number;
  escalation_rate: number;
  avg_duration_seconds: number | null;
  by_outcome: Record<string, number>;
  by_platform: Record<string, { count: number; avg_quality: number | null }>;
}

export interface ExtractionField {
  name: string;
  field_type: string;
  description: string;
  required: boolean;
  enum_values?: string[];
}

export interface ExtractionSchema {
  id: number;
  name: string;
  description: string;
  fields: ExtractionField[];
  created_at: string;
}

export interface QACohort {
  id: number;
  name: string;
  agent_filter: string | null;
  platform_filter: string | null;
  min_duration: number | null;
  max_duration: number | null;
  sampling_pct: number;
  weekly_max: number;
  criteria: Record<string, unknown>;
  created_at: string;
}

export interface CostSummary {
  total_cost_usd: number;
  by_provider: Record<string, number>;
  by_model: Record<string, number>;
  daily_costs: Record<string, unknown>[];
}

export interface HarnessResult {
  truth_score: number;
  confidence: string;
  validation_errors: string[];
  layer_scores: Record<string, number>;
}

// ── Runs ───────────────────────────────────────────────────────────────

export async function getRuns(params?: {
  search?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<RunsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.search) searchParams.set("search", params.search);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return fetchJson<RunsResponse>(`/api/v1/runs${qs ? `?${qs}` : ""}`);
}

export async function getRun(runId: string): Promise<Run> {
  return fetchJson<Run>(`/api/v1/runs/${runId}`);
}

export async function analyzeAudio(file: File): Promise<Run> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY },
    body: formData,
  });
  if (!res.ok) throw new Error(`Analysis failed: ${res.statusText}`);
  return res.json();
}

// ── Monitoring ─────────────────────────────────────────────────────────

export async function getMetrics(
  windowMinutes: number = 60
): Promise<MetricsSummary> {
  return fetchJson<MetricsSummary>(
    `/api/v1/monitoring/metrics?window_minutes=${windowMinutes}`
  );
}

// ── Alerts ─────────────────────────────────────────────────────────────

export async function getAlerts(): Promise<Alert[]> {
  return fetchJson<Alert[]>("/api/v1/monitoring/alerts");
}

export async function createAlertRule(rule: {
  name: string;
  metric: string;
  comparator: string;
  threshold: number;
  window_minutes: number;
  notify_url?: string;
  notify_email?: string;
}): Promise<{ rule_id: number; status: string }> {
  return fetchJson("/api/v1/monitoring/alerts", {
    method: "POST",
    body: JSON.stringify(rule),
  });
}

export async function deleteAlertRule(
  ruleId: number
): Promise<{ status: string }> {
  return fetchJson(`/api/v1/monitoring/alerts/${ruleId}`, {
    method: "DELETE",
  });
}

export async function getIncidents(
  limit: number = 50
): Promise<AlertIncident[]> {
  return fetchJson<AlertIncident[]>(
    `/api/v1/monitoring/incidents?limit=${limit}`
  );
}

export async function checkAlerts(): Promise<{
  triggered: unknown[];
  count: number;
}> {
  return fetchJson("/api/v1/monitoring/check", { method: "POST" });
}

// ── Extraction Schemas ────────────────────────────────────────────────

export async function getSchemas(): Promise<ExtractionSchema[]> {
  return fetchJson<ExtractionSchema[]>("/api/v1/extractions/schemas");
}

export async function createSchema(schema: {
  name: string;
  description: string;
  fields: ExtractionField[];
}): Promise<{ schema_id: number; status: string }> {
  return fetchJson("/api/v1/extractions/schemas", {
    method: "POST",
    body: JSON.stringify(schema),
  });
}

export async function deleteSchema(
  schemaId: number
): Promise<{ status: string }> {
  return fetchJson(`/api/v1/extractions/schemas/${schemaId}`, {
    method: "DELETE",
  });
}

// ── QA Cohorts ────────────────────────────────────────────────────────

export async function getQACohorts(): Promise<QACohort[]> {
  return fetchJson<QACohort[]>("/api/v1/qa/cohorts");
}

export async function createQACohort(cohort: {
  name: string;
  agent_filter?: string;
  platform_filter?: string;
  min_duration?: number;
  max_duration?: number;
  sampling_pct?: number;
  weekly_max?: number;
}): Promise<{ cohort_id: number; status: string }> {
  return fetchJson("/api/v1/qa/cohorts", {
    method: "POST",
    body: JSON.stringify(cohort),
  });
}

// ── Guardrails ────────────────────────────────────────────────────────

export async function getGuardrailStatus(): Promise<Record<string, unknown>> {
  return fetchJson("/api/v1/guardrails/status");
}

// ── Costs ──────────────────────────────────────────────────────────────

export async function getCostSummary(): Promise<CostSummary> {
  return fetchJson<CostSummary>("/api/v1/costs");
}
