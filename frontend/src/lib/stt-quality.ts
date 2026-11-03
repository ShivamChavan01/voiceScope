export interface STTSegment {
  text: string;
  speaker: string;
  role: 'caller' | 'agent' | 'unknown';
  start: number | null;
  end: number | null;
}
export interface STTTranscript {
  source: 'bolna' | 'deepgram' | 'human' | 'synthetic';
  scope: 'caller_only' | 'mixed' | 'unknown';
  segments: STTSegment[];
  audio_sha256: string | null;
  human_verified: boolean;
  verified_by: string | null;
}
export interface STTFinding {
  start: number | null;
  end: number | null;
  role: string;
  bolna_text: string;
  reference_text: string;
  category: string[];
  severity: string;
  status: 'confirmed_error' | 'needs_review';
  confidence: 'high' | 'low';
  confidence_basis: string;
  explanation: string;
  timing_basis?: 'supplied_intervals' | 'reference_anchors';
}
export interface STTAlignment {
  method: 'unique_text_anchors_v1';
  scope: 'mixed';
  timing_basis: 'reference_derived';
  speaker_roles: Record<string, 'caller' | 'agent'>;
  speaker_evidence: { speaker: string; role: 'caller' | 'agent'; matched_words: number; competing_words: number }[];
  original_token_coverage: number;
  reference_token_coverage: number;
}
export interface STTEdits {
  substitutions: number;
  deletions: number;
  insertions: number;
  reference_words: number;
}
export interface STTReview {
  schema_version: '1';
  status: 'completed' | 'partial' | 'blocked' | 'failed';
  reference_source: string | null;
  reference_human_verified: boolean;
  verified_by: string | null;
  metric_kind: 'wer' | 'estimated_disagreement' | null;
  metric_value: number | null;
  edits: STTEdits | null;
  compared_groups: number;
  findings: STTFinding[];
  issues: string[];
  limitations: string[];
  alignment?: STTAlignment | null;
}
export interface STTState {
  review: STTReview | null;
  reference: STTTranscript | null;
  bolna: STTTranscript;
  audio: { available: boolean; sha256: string | null; channels: number | null; duration_seconds: number | null; scope: string; scope_basis: string };
  provider: { name: 'deepgram'; configured: boolean; requires_consent: boolean };
}
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value); }
function strings(value: unknown): value is string[] { return Array.isArray(value) && value.every(item => typeof item === 'string'); }
function time(value: unknown): value is number | null { return value === null || typeof value === 'number' && Number.isFinite(value) && value >= 0; }
function timing(start: unknown, end: unknown): boolean {
  return start === null && end === null || typeof start === 'number' && typeof end === 'number' && Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start;
}
function hash(value: unknown): value is string | null {
  return value === null || typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
}
function isSegment(value: unknown): value is STTSegment {
  return record(value) && typeof value.text === 'string' && Boolean(value.text.trim()) && typeof value.speaker === 'string' && ['caller', 'agent', 'unknown'].includes(String(value.role)) && time(value.start) && time(value.end) && timing(value.start, value.end);
}
function isTranscript(value: unknown): value is STTTranscript {
  if (!record(value) || !['bolna', 'deepgram', 'human', 'synthetic'].includes(String(value.source)) || !['caller_only', 'mixed', 'unknown'].includes(String(value.scope)) || !Array.isArray(value.segments) || !value.segments.every(isSegment) || !hash(value.audio_sha256) || typeof value.human_verified !== 'boolean' || !(value.verified_by === null || typeof value.verified_by === 'string')) return false;
  if (value.source === 'human') return value.human_verified && value.audio_sha256 !== null && typeof value.verified_by === 'string' && Boolean(value.verified_by.trim());
  return !value.human_verified;
}
function isFinding(value: unknown): value is STTFinding {
  return record(value) && time(value.start) && time(value.end) && timing(value.start, value.end) && typeof value.role === 'string' && typeof value.bolna_text === 'string' && typeof value.reference_text === 'string' && strings(value.category) && typeof value.severity === 'string' && ['confirmed_error', 'needs_review'].includes(String(value.status)) && ['high', 'low'].includes(String(value.confidence)) && typeof value.confidence_basis === 'string' && typeof value.explanation === 'string' && (value.timing_basis === undefined || value.timing_basis === 'supplied_intervals' || value.timing_basis === 'reference_anchors');
}
function isAlignment(value: unknown): value is STTAlignment {
  if (!record(value) || value.method !== 'unique_text_anchors_v1' || value.scope !== 'mixed' || value.timing_basis !== 'reference_derived' || !record(value.speaker_roles) || !Array.isArray(value.speaker_evidence)) return false;
  const roles = value.speaker_roles;
  if (!Object.values(roles).every(role => role === 'caller' || role === 'agent') || !Object.values(roles).includes('caller') || !Object.values(roles).includes('agent')) return false;
  if (value.speaker_evidence.length !== Object.keys(roles).length || !value.speaker_evidence.every(item => record(item) && typeof item.speaker === 'string' && (item.role === 'caller' || item.role === 'agent') && roles[item.speaker] === item.role && typeof item.matched_words === 'number' && Number.isInteger(item.matched_words) && item.matched_words >= 12 && typeof item.competing_words === 'number' && Number.isInteger(item.competing_words) && item.competing_words >= 0 && item.matched_words / (item.matched_words + item.competing_words) >= .9)) return false;
  if (new Set(value.speaker_evidence.map(item=>item.speaker)).size !== Object.keys(roles).length) return false;
  return [value.original_token_coverage, value.reference_token_coverage].every(number => typeof number === 'number' && Number.isFinite(number) && number >= 0 && number <= 1);
}
function isEdits(value: unknown): value is STTEdits {
  return record(value) && ['substitutions','deletions','insertions','reference_words'].every(key => typeof value[key] === 'number' && Number.isInteger(value[key]) && value[key] >= 0);
}
export function isSTTReview(value: unknown): value is STTReview {
  if (!record(value) || value.schema_version !== '1' || !['completed', 'partial', 'blocked', 'failed'].includes(String(value.status)) || !(value.reference_source === null || ['bolna','human','deepgram','synthetic'].includes(String(value.reference_source))) || typeof value.reference_human_verified !== 'boolean' || !(value.verified_by === null || typeof value.verified_by === 'string') || !(value.metric_kind === null || value.metric_kind === 'wer' || value.metric_kind === 'estimated_disagreement') || !time(value.metric_value) || !(value.edits === null || isEdits(value.edits)) || typeof value.compared_groups !== 'number' || !Number.isInteger(value.compared_groups) || value.compared_groups < 0 || !Array.isArray(value.findings) || !value.findings.every(isFinding) || !strings(value.issues) || !strings(value.limitations)) return false;
  const verified = value.reference_human_verified && value.reference_source === 'human' && typeof value.verified_by === 'string' && Boolean(value.verified_by.trim());
  if (value.alignment !== undefined && value.alignment !== null && (!isAlignment(value.alignment) || value.metric_kind !== 'estimated_disagreement' || verified)) return false;
  if (value.findings.some(finding => finding.timing_basis === 'reference_anchors') && (!isAlignment(value.alignment) || verified || value.metric_kind !== 'estimated_disagreement')) return false;
  if (value.reference_human_verified && !verified || value.metric_kind === 'wer' && !verified || value.metric_kind === 'estimated_disagreement' && value.reference_human_verified) return false;
  if (value.findings.some(finding => finding.status === 'confirmed_error' && (!verified || finding.start === null))) return false;
  if (value.metric_value === null) return value.metric_kind === null;
  if (!value.edits || !value.edits.reference_words || !value.compared_groups) return false;
  const rate = (value.edits.substitutions + value.edits.deletions + value.edits.insertions) / value.edits.reference_words;
  return value.metric_kind !== null && value.status === 'completed' && Math.abs(value.metric_value - rate) <= 1e-10;
}
export function parseSTTState(value: unknown): STTState {
  if (record(value) && (value.review === null || isSTTReview(value.review)) && (value.reference === null || isTranscript(value.reference)) && isTranscript(value.bolna) && record(value.audio) && typeof value.audio.available === 'boolean' && hash(value.audio.sha256) && (value.audio.channels === null || typeof value.audio.channels === 'number' && Number.isInteger(value.audio.channels) && value.audio.channels > 0) && time(value.audio.duration_seconds) && typeof value.audio.scope === 'string' && typeof value.audio.scope_basis === 'string' && record(value.provider) && value.provider.name === 'deepgram' && typeof value.provider.configured === 'boolean' && typeof value.provider.requires_consent === 'boolean') {
    return { review: value.review, reference: value.reference, bolna: value.bolna, audio: {available:value.audio.available,sha256:value.audio.sha256,channels:value.audio.channels,duration_seconds:value.audio.duration_seconds,scope:value.audio.scope,scope_basis:value.audio.scope_basis}, provider:{name:value.provider.name,configured:value.provider.configured,requires_consent:value.provider.requires_consent} };
  }
  throw new Error('STT review response is invalid or unsupported. No quality score is shown.');
}
export function sttMetric(review: STTReview): { label: string; value: string } {
  if (review.metric_value === null || review.metric_kind === null) return {label:'Transcript quality',value:'Not scored'};
  if (review.reference_source === 'synthetic') return {label:'Synthetic fixture disagreement',value:`${(review.metric_value * 100).toFixed(1)}%`};
  return {label:review.metric_kind === 'wer' ? 'WER · human-verified reference' : 'Estimated transcript disagreement',value:`${(review.metric_value * 100).toFixed(1)}%`};
}
export function audioTime(seconds: number | null): string {
  if (seconds === null) return 'Timestamp unavailable';
  const tenths = Math.round(seconds * 10);
  return `${Math.floor(tenths / 600)}:${((tenths % 600) / 10).toFixed(1).padStart(4, '0')}`;
}
export function parseReviewInput(text: string): unknown {
  try { return JSON.parse(text); } catch { throw new Error('Transcript JSON is invalid. Check its syntax before submitting.'); }
}

/** Reuse only previously confirmed coverage and roles returned by the private API. */
export function savedSTTSetup(state: STTState) {
  const scope = ['mixed', 'caller_only'].includes(state.audio.scope) ? state.audio.scope : 'unknown';
  const segments = state.reference?.source === 'deepgram' ? state.reference.segments : [];
  const mapping: Record<string, string> = {};
  for (const segment of segments) {
    if (segment.role !== 'unknown') mapping[segment.speaker] = segment.role;
  }
  return { scope, scopeConfirmed: scope !== 'unknown' && state.bolna.source !== 'synthetic', mapping,
    mappingConfirmed: segments.length > 0 && segments.every(segment => segment.role !== 'unknown') };
}

export interface DisagreementPart { text: string; changed: boolean }
/** Bounded display diff. It never supplies alignment, metric counts, or timestamps. */
export function disagreementParts(left: string, right: string): [DisagreementPart[], DisagreementPart[]] {
  const a = left.match(/\s+|\S+/gu) ?? [], b = right.match(/\s+|\S+/gu) ?? [];
  if (Math.max(a.length, b.length) > 400) return [[{text:left,changed:left !== right}], [{text:right,changed:left !== right}]];
  const lengths = Array.from({length:a.length + 1}, () => new Uint16Array(b.length + 1));
  for (let i=a.length-1;i>=0;i--) for(let j=b.length-1;j>=0;j--) lengths[i][j] = a[i] === b[j] ? lengths[i+1][j+1]+1 : Math.max(lengths[i+1][j],lengths[i][j+1]);
  const first: DisagreementPart[] = [], second: DisagreementPart[] = [];
  let i=0,j=0;
  while(i<a.length || j<b.length) {
    if(i<a.length && j<b.length && a[i] === b[j]) { first.push({text:a[i++],changed:false}); second.push({text:b[j++],changed:false}); }
    else if(i<a.length && (j===b.length || lengths[i+1][j] >= lengths[i][j+1])) first.push({text:a[i++],changed:true});
    else second.push({text:b[j++],changed:true});
  }
  return [first,second];
}
