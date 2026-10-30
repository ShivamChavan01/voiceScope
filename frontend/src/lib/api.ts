import { parseSTTState, type STTReview } from "./stt-quality";
import { requestErrorMessage, type PolicyRule, type ReliabilityReport, type ReliabilitySummary, type SpeechDiagnostics } from "./reliability";

// Use local proxy to avoid CORS — /api/[...path] forwards to Railway backend

const API_BASE = "";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let body: unknown = null;
    try { body = await res.json(); } catch { /* Non-JSON errors use the HTTP status. */ }
    throw new Error(requestErrorMessage(body, res.status, res.statusText));
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
  transcript_preview: string | null;
  transcript_speakers: { speaker: number; text: string; role?: string; label?: string; role_source?: string }[] | null;
  layer_scores: Record<string, number> | null;
  hallucination_evidence: string | null;
  policy_evidence: string | null;
  status: string;
  created_at: string;
  reliability_summary?: ReliabilitySummary | null;
  evaluation?: {
    reliability?: ReliabilityReport;
    stt_quality?: STTReview;
    speech_diagnostics?: SpeechDiagnostics;
    data_source?: string;
    source_call?: { call_id?: string; agent_id?: string; platform?: string };
    report?: { executive_summary?: string };
    raw_transcript?: string;
    evaluation_status?: "failed" | "needs_review" | "validated" | "deterministic_checks_completed";
    errors?: string[];
    harness?: { validation_passed: boolean; validation_errors: string[] };
  };
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

export async function deleteRun(runId: string): Promise<{ status: string }> {
  return fetchJson(`/api/v1/runs/${runId}`, { method: "DELETE" });
}

export async function getRunHistory(
  limit: number = 12
): Promise<{ scores: number[]; count: number }> {
  return fetchJson(`/api/v1/runs/history?limit=${limit}`);
}

export interface StreamEvent {
  event: "started" | "stage_complete" | "complete" | "error";
  run_id?: string;
  stage?: string;
  result?: { run_id: string; status: string };
  detail?: string;
}

export async function analyzeAudio(file: File): Promise<Run> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Analysis failed: ${res.statusText}`);
  return res.json();
}

function analysisFrame(frame: string): StreamEvent | null {
  const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).replace(/^ /, '')).join('\n');
  if (!data) return null;
  let value: unknown;
  try { value = JSON.parse(data); } catch { throw new Error('Analysis returned an invalid progress event. Retry the upload.'); }
  if (typeof value !== 'object' || value === null || !('event' in value)) throw new Error('Analysis returned an invalid progress event.');
  if (value.event === 'started' && 'run_id' in value && typeof value.run_id === 'string' && value.run_id.trim()) return {event:'started',run_id:value.run_id};
  if (value.event === 'stage_complete' && 'stage' in value && typeof value.stage === 'string' && ['transcription','analysis','report','harness'].includes(value.stage)) return {event:'stage_complete',stage:value.stage};
  if (value.event === 'error' && 'detail' in value && typeof value.detail === 'string' && value.detail.trim()) return {event:'error',detail:value.detail};
  if (value.event === 'complete' && 'result' in value && typeof value.result === 'object' && value.result !== null && 'run_id' in value.result && typeof value.result.run_id === 'string' && value.result.run_id.trim() && 'status' in value.result && typeof value.result.status === 'string' && ['completed','partial','failed'].includes(value.result.status)) return {event:'complete',result:{run_id:value.result.run_id,status:value.result.status}};
  throw new Error('Analysis returned an invalid progress event or missing result.');
}

export async function* analyzeAudioStream(file: File): AsyncGenerator<StreamEvent> {
  const formData = new FormData();
  formData.append('file', file);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  try {
    const res = await fetch(`${API_BASE}/api/v1/analyze/stream`, {method:'POST',body:formData,signal:controller.signal});
    if (!res.ok) {
      let body: unknown = null;
      try { body = await res.json(); } catch { /* Some proxies return a non-JSON error. */ }
      throw new Error(requestErrorMessage(body, res.status, res.statusText));
    }
    if (!res.headers.get('content-type')?.includes('text/event-stream')) throw new Error('Analysis did not return a progress stream. Retry the upload.');
    reader = res.body?.getReader();
    if (!reader) throw new Error('Analysis returned no response body. Retry the upload.');
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const {done,value} = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value,{stream:true});
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || '';
      if (done && buffer.trim()) { frames.push(buffer); buffer = ''; }
      for (const frame of frames) {
        const event = analysisFrame(frame);
        if (!event) continue;
        yield event;
        if (event.event === 'complete' || event.event === 'error') return;
      }
      if (done) throw new Error('Analysis stream ended before a result was returned. Retry the upload.');
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw new Error('Analysis timed out. Retry the upload.');
    throw error;
  } finally {
    clearTimeout(timeout);
    controller.abort();
    reader?.releaseLock();
  }
}

// ── Monitoring ─────────────────────────────────────────────────────────

export interface CostSummary {
  overall: {
    total_cost: number | null;
    total_input: number | null;
    total_output: number | null;
    total_calls: number | null;
  };
  by_provider: Record<string, { cost: number; calls: number; input_tokens: number; output_tokens: number }>;
  by_model: Record<string, { cost: number; calls: number }>;
}

export async function getCosts(): Promise<CostSummary> {
  return fetchJson<CostSummary>("/api/v1/costs");
}

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

// ── Demo ────────────────────────────────────────────────────────────

export async function seedDemo(): Promise<{ seeded: number; total_runs: number }> {
  return fetchJson("/api/v1/demo/seed", { method: "POST" });
}

export async function resetDemo(): Promise<{ reset: boolean; removed: number }> {
  return fetchJson("/api/v1/demo/reset", { method: "POST" });
}

// ── Knowledge Base ───────────────────────────────────────────────────

export interface KnowledgeEntry {
  id: number;
  title: string;
  content: string;
  created_at: string;
}

export async function getKnowledge(): Promise<KnowledgeEntry[]> {
  return fetchJson("/api/v1/knowledge");
}

export async function createKnowledge(entry: {
  title: string;
  content: string;
}): Promise<{ entry_id: number; status: string }> {
  return fetchJson("/api/v1/knowledge", {
    method: "POST",
    body: JSON.stringify(entry),
  });
}

export async function deleteKnowledge(entryId: number): Promise<{ status: string }> {
  return fetchJson(`/api/v1/knowledge/${entryId}`, { method: "DELETE" });
}

// ── Self-Improvement Loop ────────────────────────────────────────────

export interface BenchmarkSummary {
  total_tests: number;
  avg_truth_score: number;
  sentiment_accuracy: number;
  outcome_accuracy: number;
  hallucination_accuracy: number | null;
  escalation_accuracy: number;
  avg_citation_coverage: number;
  avg_fact_accuracy: number | null;
  weakest_layer: string;
  strongest_layer: string;
}

export async function getBenchmark(): Promise<BenchmarkSummary> {
  return fetchJson("/api/v1/loop/benchmark");
}

export async function getLoopStatus(): Promise<{
  optimizer_weights: Record<string, number>;
  optimization_history: number;
  prompt_stats: unknown[];
  suggestions: unknown[];
}> {
  return fetchJson("/api/v1/loop/status");
}

export async function runLoop(): Promise<{
  status: string;
  benchmark: BenchmarkSummary;
  optimization: { improvement: number; changes: unknown[] };
  suggestions: unknown[];
}> {
  return fetchJson("/api/v1/loop/run", { method: "POST" });
}

export async function getWeights(): Promise<{
  weights: Record<string, number>;
  history: number;
}> {
  return fetchJson("/api/v1/loop/weights");
}

export interface RunSummary {
  total_calls: number;
  real_calls: number;
  demo_calls: number;
  completed_calls: number;
  evaluated_real_calls: number;
  flagged_calls: number;
  escalated_calls: number;
  hallucination_rate: number | null;
  escalation_rate: number | null;
  confirmed_policy_calls: number;
  review_calls: number;
  evaluated_policy_calls: number;
  legacy_calls: number;
  scope: "all_time_persisted_runs";
}

export async function getRunSummary(): Promise<RunSummary> {
  return fetchJson("/api/v1/runs/summary");
}

export async function getPolicyRules(): Promise<PolicyRule[]> {
  return fetchJson("/api/v1/policies/rules");
}
export async function savePolicyRule(rule: Omit<PolicyRule, "version">): Promise<PolicyRule> {
  return fetchJson("/api/v1/policies/rules", { method: "POST", body: JSON.stringify(rule) });
}
export async function deletePolicyRule(id: string): Promise<{ status: string }> {
  return fetchJson(`/api/v1/policies/rules/${encodeURIComponent(id)}`, { method: "DELETE" });
}
export async function loadReviewDemo(): Promise<{ seeded: number; run_ids: string[] }> {
  return fetchJson("/api/v1/demo/reliability", { method: "POST" });
}

export interface DetectionMetrics {
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
}

export interface BenchmarkFinding {
  category: 'policy_violation' | 'unverified_claim' | 'insufficient_evidence';
  status: 'confirmed' | 'needs_review';
  policy_kind: string | null;
  severity: string;
  turn_indices: number[];
  missing_evidence: string[];
}

export interface PolicyBenchmark {
  benchmark_kind: 'policy_detector_labeled';
  dataset_version: string;
  dataset_sha256: string;
  data_source: 'synthetic_hand_labeled';
  total_cases: number;
  passed_cases: number;
  exact_case_accuracy: number;
  supported_cases: number;
  supported_passed: number;
  challenge_cases: number;
  challenge_passed: number;
  metrics: DetectionMetrics;
  by_category: Record<string, DetectionMetrics>;
  results: {
    id: string;
    name: string;
    purpose: string;
    scope: string;
    passed: boolean;
    turns: { speaker: number; role: string; role_source: string; text: string }[];
    policies: PolicyRule[];
    expected_status: string;
    actual_status: string;
    expected: BenchmarkFinding[];
    actual: BenchmarkFinding[];
    evidence_errors: string[];
  }[];
  limitations: string[];
}

export async function getPolicyBenchmark(): Promise<PolicyBenchmark> {
  return fetchJson('/api/v1/loop/benchmark/reliability');
}


export async function getSTTReview(runId: string) {
  return parseSTTState(await fetchJson<unknown>(`/api/v1/runs/${encodeURIComponent(runId)}/stt-review`));
}
export async function generateSTTReference(runId: string) {
  return parseSTTState(await fetchJson<unknown>(`/api/v1/runs/${encodeURIComponent(runId)}/stt-review/reference`, {method:'POST',body:JSON.stringify({provider:'deepgram'})}));
}
export async function evaluateSTT(runId: string, body: unknown) {
  return parseSTTState(await fetchJson<unknown>(`/api/v1/runs/${encodeURIComponent(runId)}/stt-review`, {method:'POST',body:JSON.stringify(body)}));
}

export async function retrieveSTTRecording(runId: string) {
  return parseSTTState(await fetchJson<unknown>(`/api/v1/runs/${encodeURIComponent(runId)}/stt-review/recording`, {method:'POST'}));
}

export async function prepareSTTReview(runId: string) {
  const state = await getSTTReview(runId);
  const eligible = !runId.startsWith('demo-') && state.provider.configured && state.bolna.segments.length > 0;
  if (eligible && !state.reference && state.review?.status !== 'failed') return generateSTTReference(runId);
  return state;
}
