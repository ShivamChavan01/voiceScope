import type { Run } from './api';

export type PolicyKind = 'no_same_day_refund_guarantee' | 'honor_escalation_request';
export interface PolicyRule {
  id: string;
  title: string;
  kind: PolicyKind;
  text: string;
  enabled: boolean;
  version: string;
}
export interface PolicySnapshot {
  id: string;
  title: string;
  kind: PolicyKind;
  text: string;
  version: string;
}
export interface FindingEvidence {
  turn_index: number;
  speaker_role: string;
  role_source: string;
  quote: string;
}
export interface ReliabilityFinding {
  id: string;
  category: 'policy_violation' | 'unverified_claim' | 'insufficient_evidence';
  status: 'confirmed' | 'needs_review';
  severity: 'high' | 'medium' | 'info';
  title: string;
  explanation: string;
  evidence: FindingEvidence[];
  policy_id: string | null;
  missing_evidence: string[];
}
export interface ReliabilityReport {
  schema_version: '1';
  status: 'assessed' | 'insufficient_evidence';
  checked_rule_ids: string[];
  policy_snapshots: PolicySnapshot[];
  findings: ReliabilityFinding[];
  limitations: string[];
}
export interface ReliabilitySummary {
  status: 'assessed' | 'insufficient_evidence';
  checked_rule_count: number;
  finding_count: number;
  confirmed_policy_count: number;
  review_count: number;
  unverified_claim_count: number;
}
export interface SpeechDiagnostics {
  source: 'bolna' | 'unavailable';
  time_to_first_audio_ms: number | null;
  transcriber_ms: number | null;
  llm_ms: number | null;
  synthesizer_ms: number | null;
  total_interruptions: number | null;
  agent_interrupted_user_count: number | null;
  user_interrupted_agent_count: number | null;
  hangup_reason: string | null;
  hangup_by: string | null;
  limitations: string[];
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string');
}
function kind(value: unknown): value is PolicyKind {
  return value === 'no_same_day_refund_guarantee' || value === 'honor_escalation_request';
}
function snapshot(value: unknown): value is PolicySnapshot {
  return record(value) && typeof value.id === 'string' && typeof value.title === 'string' && kind(value.kind)
    && typeof value.text === 'string' && typeof value.version === 'string';
}
function evidence(value: unknown): value is FindingEvidence {
  return record(value) && typeof value.turn_index === 'number' && Number.isInteger(value.turn_index) && value.turn_index >= 0
    && typeof value.speaker_role === 'string' && typeof value.role_source === 'string' && typeof value.quote === 'string';
}
function finding(value: unknown): value is ReliabilityFinding {
  return record(value) && typeof value.id === 'string' && typeof value.title === 'string'
    && typeof value.explanation === 'string' && (value.category === 'policy_violation' || value.category === 'unverified_claim' || value.category === 'insufficient_evidence')
    && (value.status === 'confirmed' || value.status === 'needs_review')
    && (value.severity === 'high' || value.severity === 'medium' || value.severity === 'info')
    && Array.isArray(value.evidence) && value.evidence.every(evidence)
    && (value.policy_id === null || typeof value.policy_id === 'string') && strings(value.missing_evidence);
}
export function readReliability(value: unknown): ReliabilityReport | null {
  if (!record(value) || value.schema_version !== '1' || (value.status !== 'assessed' && value.status !== 'insufficient_evidence')) return null;
  if (!strings(value.checked_rule_ids) || !strings(value.limitations) || !Array.isArray(value.policy_snapshots)
    || !value.policy_snapshots.every(snapshot) || !Array.isArray(value.findings) || !value.findings.every(finding)) return null;
  return {
    schema_version: value.schema_version, status: value.status, checked_rule_ids: value.checked_rule_ids,
    policy_snapshots: value.policy_snapshots, findings: value.findings, limitations: value.limitations,
  };
}
function nullableMetric(value: unknown): value is number | null {
  return value === null || (typeof value === 'number' && Number.isFinite(value) && value >= 0);
}
export function readSpeech(value: unknown): SpeechDiagnostics | null {
  if (!record(value) || (value.source !== 'bolna' && value.source !== 'unavailable') || !strings(value.limitations)) return null;
  if (!nullableMetric(value.time_to_first_audio_ms) || !nullableMetric(value.transcriber_ms) || !nullableMetric(value.llm_ms)
    || !nullableMetric(value.synthesizer_ms) || !nullableMetric(value.total_interruptions)
    || !nullableMetric(value.agent_interrupted_user_count) || !nullableMetric(value.user_interrupted_agent_count)
    || !(value.hangup_reason === null || typeof value.hangup_reason === 'string')
    || !(value.hangup_by === null || typeof value.hangup_by === 'string')) return null;
  return {
    source: value.source, time_to_first_audio_ms: value.time_to_first_audio_ms,
    transcriber_ms: value.transcriber_ms, llm_ms: value.llm_ms, synthesizer_ms: value.synthesizer_ms,
    total_interruptions: value.total_interruptions, agent_interrupted_user_count: value.agent_interrupted_user_count,
    user_interrupted_agent_count: value.user_interrupted_agent_count, hangup_reason: value.hangup_reason,
    hangup_by: value.hangup_by, limitations: value.limitations,
  };
}
export function reportSummary(report: ReliabilityReport): ReliabilitySummary {
  return {
    status: report.status, checked_rule_count: report.checked_rule_ids.length, finding_count: report.findings.length,
    confirmed_policy_count: report.findings.filter(item => item.category === 'policy_violation' && item.status === 'confirmed').length,
    review_count: report.findings.filter(item => item.status === 'needs_review').length,
    unverified_claim_count: report.findings.filter(item => item.category === 'unverified_claim').length,
  };
}
export function readSummary(value: unknown): ReliabilitySummary | null {
  if (!record(value) || (value.status !== 'assessed' && value.status !== 'insufficient_evidence')) return null;
  const count = (item: unknown): item is number => typeof item === 'number' && Number.isInteger(item) && item >= 0;
  if (!count(value.checked_rule_count) || !count(value.finding_count) || !count(value.confirmed_policy_count)
    || !count(value.review_count) || !count(value.unverified_claim_count)) return null;
  return { status: value.status, checked_rule_count: value.checked_rule_count, finding_count: value.finding_count,
    confirmed_policy_count: value.confirmed_policy_count, review_count: value.review_count,
    unverified_claim_count: value.unverified_claim_count };
}
export type ReviewVerdict = { kind: 'confirmed' | 'review' | 'no_matches' | 'insufficient' | 'not_assessed'; label: string; detail: string };
export function reviewVerdict(run: Pick<Run, 'evaluation' | 'reliability_summary'>): ReviewVerdict {
  const report = readReliability(run.evaluation?.reliability);
  const summary = report ? reportSummary(report) : readSummary(run.reliability_summary);
  if (!summary) return { kind: 'not_assessed', label: 'Not assessed', detail: 'No structured policy assessment is stored for this call.' };
  if (summary.confirmed_policy_count > 0) return { kind: 'confirmed', label: `${summary.confirmed_policy_count} policy ${summary.confirmed_policy_count === 1 ? 'match' : 'matches'}`, detail: 'A recorded statement matches a configured prohibition. Review its quote and policy.' };
  if (summary.review_count > 0 || summary.unverified_claim_count > 0) return { kind: 'review', label: 'Needs evidence review', detail: 'Some claims or speaker roles lack sufficient corroborating evidence.' };
  if (summary.status === 'insufficient_evidence' || summary.checked_rule_count === 0) return { kind: 'insufficient', label: 'Insufficient evidence', detail: 'Configure supported policies and supply an attributed transcript to assess this call.' };
  return { kind: 'no_matches', label: `No matches in ${summary.checked_rule_count} supported ${summary.checked_rule_count === 1 ? 'check' : 'checks'}`, detail: 'This result covers only the configured supported checks. It does not establish overall compliance.' };
}
export function categoryLabel(category: ReliabilityFinding['category']): string {
  switch (category) {
    case 'policy_violation': return 'Policy match';
    case 'unverified_claim': return 'Unverified claim';
    case 'insufficient_evidence': return 'Insufficient evidence';
  }
}
export function formatMetric(value: number | null | undefined, unit: 'ms' | 'count' = 'ms'): string {
  if (value == null || !Number.isFinite(value) || value < 0) return 'Unavailable';
  return unit === 'count' ? String(value) : `${Math.round(value).toLocaleString()} ms`;
}
export function formatDuration(value: number | null): string {
  if (value == null || !Number.isFinite(value) || value < 0) return 'Unavailable';
  return `${Math.floor(value / 60)}m ${String(Math.floor(value % 60)).padStart(2, '0')}s`;
}
export function relativeTime(value: string, now = Date.now()): string {
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  const date = new Date(normalized).getTime();
  if (!Number.isFinite(date)) return 'Date unavailable';
  const minutes = Math.max(0, Math.floor((now - date) / 60000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
  return `${Math.floor(minutes / 1440)}d ago`;
}

export function requestErrorMessage(body: unknown, status: number, statusText: string): string {
  if (record(body) && typeof body.detail === 'string' && body.detail.trim()) return body.detail;
  if (record(body) && Array.isArray(body.detail)) {
    const messages = body.detail.filter(record).map(item => typeof item.msg === 'string' ? item.msg : '').filter(Boolean);
    if (messages.length) return messages.join('; ');
  }
  return `Request failed (${status}${statusText ? ` ${statusText}` : ''}).`;
}

interface ProcessingEvent {
  event: string;
  stage?: string;
  result?: { status?: string };
  detail?: string;
}
export function processingProgress(events: ProcessingEvent[], error?: string): {
  activeStage: string | null;
  completedStages: string[];
  terminal: 'failed' | 'review' | 'complete' | null;
  message: string | null;
} {
  const stages = ['transcription', 'analysis', 'report'];
  const completedStages = stages.filter(stage => events.some(event => event.event === 'stage_complete' && event.stage === stage));
  const failure = events.find(event => event.event === 'error');
  const result = events.findLast(event => event.event === 'complete')?.result;
  if (error || failure || result?.status === 'failed') return { activeStage: null, completedStages, terminal: 'failed', message: error || failure?.detail || 'Evaluation failed. Open the stored run for details.' };
  if (result) return { activeStage: null, completedStages, terminal: result.status === 'partial' ? 'review' : 'complete', message: result.status === 'partial' ? 'Processed · review required' : 'Processing complete' };
  return { activeStage: events.some(event => event.event === 'started') ? stages.find(stage => !completedStages.includes(stage)) || null : null, completedStages, terminal: null, message: null };
}
