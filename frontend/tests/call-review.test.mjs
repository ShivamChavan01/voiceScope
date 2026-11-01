import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

async function component(file, replacements) {
  const source = await readFile(new URL(`../src/components/${file}`, import.meta.url), 'utf8');
  let js = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext } }).outputText;
  for (const [from, to] of Object.entries({ 'react/jsx-runtime': import.meta.resolve('react/jsx-runtime'), 'lucide-react': import.meta.resolve('lucide-react'), ...replacements })) {
    js = js.replaceAll(`'${from}'`, JSON.stringify(to)).replaceAll(`"${from}"`, JSON.stringify(to));
  }
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
}
const { CallReport, CallSummary, FindingsPanel, ReviewBadge } = await component('call-review.tsx', {
  'next/link': import.meta.resolve('next/link.js'),
  '@/lib/reliability': new URL('../src/lib/reliability.ts', import.meta.url).href,
});
const report = { schema_version: '1', status: 'insufficient_evidence', checked_rule_ids: [], policy_snapshots: [], findings: [], limitations: ['No supported company policies are enabled.'] };
const base = { run_id: 'synthetic-ui-fixture', status: 'partial', evaluation: { reliability: report } };
const render = (Component, run) => renderToStaticMarkup(createElement(Component, { run, onEvidence() {}, onChecks() {} }));

test('validation review does not falsely claim that call processing failed to complete', () => {
  const run = { ...base, evaluation: { ...base.evaluation, evaluation_status: 'needs_review', errors: [], harness: { validation_errors: ['Unsupported analysis claim'] } } };
  const html = render(CallSummary, run);
  assert.doesNotMatch(html, /processing did not complete/);
  assert.match(html, /Evaluation requires review/);
});

test('saved model summaries and evaluator warnings are visible without becoming confirmed call violations', () => {
  const run = { ...base, provider: 'groq', intent: 'request a supervisor', outcome: 'escalated', sentiment: 'negative', evaluation: {
    ...base.evaluation, report: { executive_summary: 'Synthetic model summary <draft>.' },
    harness: { validation_errors: ['analysis numeric claim 90 is absent from transcript'] },
  } };
  const html = render(CallReport, run);
  for (const text of ['Call summary', 'AI-generated', 'Needs review', 'Synthetic model summary &lt;draft&gt;.', 'model reported', 'analysis numeric claim 90', 'View evaluation checks']) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /Confirmed|Clean|verified facts|truth score/);
  const noWarnings = render(CallReport, { ...run, status: 'completed', evaluation: { report: { executive_summary: 'Stored summary' } } });
  assert.match(noWarnings, /Stored summary/);
  assert.doesNotMatch(noWarnings, /evaluation warning|View evaluation checks|Needs review/);
});

test('missing, synthetic, failed and non-model reports do not invent a generated call summary', () => {
  const report = { executive_summary: 'Synthetic import notice' };
  for (const run of [base, { ...base, evaluation: { report } }, { ...base, provider: 'synthetic', evaluation: { report } }, { ...base, status: 'failed', provider: 'groq', evaluation: { report } }, { ...base, provider: 'groq', evaluation: { report: { executive_summary: {} } } }, { ...base, provider: 'groq', evaluation: { report: { executive_summary: ' ' } } }]) assert.equal(render(CallReport, run), '');
});

test('call summary explains absent policy configuration once and preserves the review state', () => {
  const html = render(CallSummary, base);
  assert.match(html, /Policy checks unavailable/);
  assert.match(html, /No supported company policies were enabled/);
  assert.match(html, /Evaluation requires review/);
  assert.match(html, /href="\/settings"/);
  assert.equal((html.match(/<h2>/g) || []).length, 1);
  assert.doesNotMatch(html, /Clean|compliant|More evidence is needed/);
});

test('missing assessments and failed processing remain explicit without blaming policy configuration', () => {
  const html = render(CallSummary, { run_id: 'legacy', status: 'failed' });
  assert.match(html, /Not assessed/);
  assert.match(html, /Processing failed/);
  assert.doesNotMatch(html, /No supported company policies|Set up policies/);
  assert.match(render(CallSummary, { ...base, run_id: 'demo-example' }), /Synthetic scenario/);
  const checked = { ...base, status: 'completed', evaluation: { reliability: { ...report, status: 'assessed', checked_rule_ids: ['stored-rule'] } } };
  assert.doesNotMatch(render(CallSummary, checked), /No supported company policies|Policy checks unavailable/);
  assert.match(render(CallSummary, checked), /No matches in 1 supported check/);
});

const finding = { id: 'promise', category: 'unverified_claim', status: 'needs_review', severity: 'high', title: 'Refund completion claim', explanation: 'Successful tool evidence is missing.', evidence: [{ turn_index: 2, speaker_role: 'agent', role_source: 'transcript_label', quote: 'I completed the refund.' }], policy_id: null, missing_evidence: ['successful_tool_result'] };
test('missing policy snapshots never hide recorded findings or their evidence', () => {
  const run = { ...base, evaluation: { reliability: { ...report, findings: [finding] } } };
  const summary = render(CallSummary, run);
  assert.match(summary, /Needs evidence review/);
  assert.doesNotMatch(summary, /Policy checks unavailable/);
  const html = render(FindingsPanel, run);
  for (const text of ['Refund completion claim', 'I completed the refund.', 'Turn 3', 'successful tool result', 'Needs review']) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /Confirmed rule match/);
});

test('empty findings use one short state and keep assessment limits visible without claiming compliance', () => {
  const html = render(FindingsPanel, base);
  assert.match(html, /No policy findings recorded/);
  assert.match(html, /does not establish compliance/);
  assert.match(html, /<section class="review-limitations"><h3>Assessment scope and limitations<\/h3>/);
  assert.doesNotMatch(html, /More evidence is needed|0 recorded|<details[^>]*open/);
  assert.match(render(FindingsPanel, { status: 'completed' }), /No structured assessment stored/);
  assert.match(render(ReviewBadge, base), /Insufficient evidence/);
});

test('authored hallucination fixture shows its provenance and exact turn evidence', () => {
  const fixture={...base,run_id:'demo-staging-hallucination',provider:'synthetic',transcript_speakers:[
    {speaker:0,role:'customer',text:'My receipt total is $100.'},
    {speaker:1,role:'agent',text:'Your total is $900.'},
  ],evaluation:{data_source:'synthetic_demo',synthetic_contradiction:{source_turn:0,claim_turn:1}}};
  const html=render(FindingsPanel,fixture);
  for(const text of ['Hand-labeled fixture','No live model detector ran','$100','$900','Turn 1','Turn 2']) assert.ok(html.includes(text),text);
  assert.doesNotMatch(html,/Confirmed rule match|AI-generated/);
  for(const changed of [{provider:'groq'},{run_id:'real-call'},{evaluation:{...fixture.evaluation,synthetic_contradiction:{source_turn:99,claim_turn:1}}}]) {
    assert.doesNotMatch(render(FindingsPanel,{...fixture,...changed}),/Hand-labeled fixture/);
  }
});

const fakeApi = `data:text/javascript,${encodeURIComponent('export async function getSTTReview(){throw new Error("SSR must not fetch")}; export async function retrieveSTTRecording(){throw new Error("SSR must not fetch")}')}`;
const { CallRecording } = await component('call-recording.tsx', { react: import.meta.resolve('react'), '../lib/api': fakeApi });
test('recording panel never invents retained audio or fetches during server rendering', () => {
  assert.match(render(CallRecording, { run_id: 'upload' }), /Playback is available for linked Bolna recordings/);
  assert.doesNotMatch(render(CallRecording, { run_id: 'upload' }), /<audio|Load recording/);
  const html = render(CallRecording, { run_id: 'bolna', evaluation: { source_call: { platform: 'bolna', call_id: 'execution' } } });
  assert.match(html, /Loading recording/);
  assert.doesNotMatch(html, /<audio|Deepgram|transcrib/);
});
