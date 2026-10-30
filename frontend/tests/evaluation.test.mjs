import assert from 'node:assert/strict';
import { test } from 'node:test';
import { runVerdict, validScore } from '../src/lib/evaluation.ts';

const run = { run_id: 'real-1', status: 'completed', hallucination_detected: 0, layer_scores: {} };

test('a negative flag never claims compliance', () => {
  assert.equal(runVerdict(run), 'Not flagged · unverified');
});
test('demo, failure and review states take precedence', () => {
  assert.equal(runVerdict({ ...run, run_id: 'demo-001' }), 'Synthetic demo');
  assert.equal(runVerdict({ ...run, status: 'failed' }), 'Evaluation failed');
  assert.equal(runVerdict({ ...run, status: 'partial' }), 'Needs review');
  assert.equal(runVerdict({ ...run, evaluation: { harness: { validation_passed: false } } }), 'Needs review');
});
test('legacy invalid scores and model flags are explicit', () => {
  assert.equal(runVerdict({ ...run, layer_scores: { facts: -2.79 } }), 'Invalid legacy scores');
  assert.equal(runVerdict({ ...run, hallucination_detected: 1 }), 'Model flagged');
});
test('valid scores pass through without hidden caps', () => {
  assert.equal(validScore(0.95), 0.95);
  assert.equal(validScore(0), 0);
  assert.equal(validScore(1), 1);
  for (const value of [null, -1, 2, NaN, Infinity]) assert.equal(validScore(value), null);
});

test('a zero layer score fails; only absent data is unassessed', async () => {
  const { layerStatus } = await import('../src/lib/evaluation.ts');
  assert.equal(layerStatus(0), 'fail');
  assert.equal(layerStatus(null), 'na');
  assert.equal(layerStatus(-279), 'invalid');
  assert.equal(layerStatus(101), 'invalid');
  assert.equal(layerStatus(NaN), 'invalid');
  assert.equal(layerStatus(50), 'warning');
  assert.equal(layerStatus(80), 'pass');
});

test('speaker labels separate explicit roles, inference, and unknown identity', async () => {
  const { speakerLabel } = await import('../src/lib/evaluation.ts');
  const turn = { speaker: 0, text: 'Hello' };
  assert.equal(speakerLabel({ ...turn, role: 'customer', role_source: 'transcript_label' }), 'Customer');
  assert.equal(speakerLabel({ ...turn, role: 'agent', role_source: 'model_inference' }), 'Agent · inferred');
  assert.equal(speakerLabel({ ...turn, role: 'agent' }), 'Agent · unverified');
  assert.equal(speakerLabel({ ...turn, label: 'Caller 1' }), 'Speaker 0 · role unknown');
  assert.equal(speakerLabel({ ...turn, role: 'boss', label: 'Verified customer' }), 'Speaker 0 · role unknown');
});
