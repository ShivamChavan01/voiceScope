import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readReliability, readSpeech, reviewVerdict, formatMetric, relativeTime } from '../src/lib/reliability.ts';

const report = { schema_version: '1', status: 'assessed', checked_rule_ids: ['refund'], policy_snapshots: [], findings: [], limitations: [] };
const finding = { id: 'one', category: 'policy_violation', status: 'confirmed', severity: 'high', title: 'Forbidden promise', explanation: 'Quote contradicts policy', evidence: [{ turn_index: 0, speaker_role: 'agent', role_source: 'transcript_label', quote: 'Guaranteed today' }], policy_id: 'refund', missing_evidence: [] };

test('assessment absence cannot become a clean verdict', () => {
  assert.equal(reviewVerdict({}).kind, 'not_assessed');
  assert.equal(reviewVerdict({ evaluation: { reliability: { ...report, checked_rule_ids: [] } } }).kind, 'insufficient');
  assert.equal(reviewVerdict({ evaluation: { reliability: report } }).label, 'No matches in 1 supported check');
});
test('policy findings remain visible when model processing fails', () => {
  const result = reviewVerdict({ status: 'failed', evaluation: { reliability: { ...report, findings: [finding] } } });
  assert.equal(result.kind, 'confirmed');
});
test('unverified claims and inferred attribution require review', () => {
  const unverified = { ...finding, category: 'unverified_claim', status: 'needs_review', policy_id: null, missing_evidence: ['action_result'] };
  assert.equal(reviewVerdict({ evaluation: { reliability: { ...report, findings: [unverified] } } }).kind, 'review');
});
test('malformed evidence and future schemas are rejected', () => {
  assert.equal(readReliability({ ...report, schema_version: '2' }), null);
  assert.equal(readReliability({ ...report, findings: [{ ...finding, evidence: [{ ...finding.evidence[0], turn_index: -1 }] }] }), null);
  assert.equal(readReliability({ ...report, findings: [{ ...finding, category: 'clean' }] }), null);
});
test('missing speech metrics remain unavailable and zero stays measured', () => {
  assert.equal(formatMetric(null), 'Unavailable');
  assert.equal(formatMetric(-1), 'Unavailable');
  assert.equal(formatMetric(NaN), 'Unavailable');
  assert.equal(formatMetric(0), '0 ms');
  assert.equal(formatMetric(0, 'count'), '0');
  assert.equal(readSpeech({ source: 'bolna' }), null);
});
test('timestamp offsets are preserved', () => {
  const now = Date.parse('2026-10-25T12:00:00Z');
  assert.equal(relativeTime('2026-10-25T11:00:00+00:00', now), '1h ago');
  assert.equal(relativeTime('2026-10-25T11:00:00', now), '1h ago');
  assert.equal(relativeTime('broken', now), 'Date unavailable');
});

test('policy validation failures are visible to the person configuring a rule', async () => {
  const { requestErrorMessage } = await import('../src/lib/reliability.ts');
  assert.equal(requestErrorMessage({ detail: 'Policy must prohibit same-day guarantees.' }, 422, ''), 'Policy must prohibit same-day guarantees.');
  assert.equal(requestErrorMessage({ detail: [{ msg: 'Title is required' }] }, 422, ''), 'Title is required');
  assert.equal(requestErrorMessage(null, 503, ''), 'Request failed (503).');
});

test('upload progress marks exactly one next stage and preserves failure states', async () => {
  const { processingProgress } = await import('../src/lib/reliability.ts');
  assert.equal(processingProgress([]).activeStage, null);
  assert.equal(processingProgress([{ event: 'started' }]).activeStage, 'transcription');
  const transcribed = [{ event: 'started' }, { event: 'stage_complete', stage: 'transcription' }];
  assert.equal(processingProgress(transcribed).activeStage, 'analysis');
  assert.equal(processingProgress([...transcribed, { event: 'complete', result: { status: 'failed' } }]).terminal, 'failed');
  assert.equal(processingProgress([...transcribed, { event: 'complete', result: { status: 'partial' } }]).terminal, 'review');
  assert.equal(processingProgress([...transcribed, { event: 'complete', result: { status: 'completed' } }]).terminal, 'complete');
  assert.equal(processingProgress(transcribed, 'Network disconnected').message, 'Network disconnected');
});

test('summary-only list verdicts validate counts before making claims', async () => {
  const { readSummary } = await import('../src/lib/reliability.ts');
  const summary = { status: 'assessed', checked_rule_count: 2, finding_count: 1, confirmed_policy_count: 1, review_count: 0, unverified_claim_count: 0 };
  assert.equal(reviewVerdict({ reliability_summary: summary }).kind, 'confirmed');
  assert.equal(readSummary({ ...summary, confirmed_policy_count: -1 }), null);
  assert.equal(reviewVerdict({ reliability_summary: { ...summary, confirmed_policy_count: 'one' } }).kind, 'not_assessed');
});
