// Synthetic UI regression: all API responses are intercepted, no provider uploads.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
const base = process.env.STT_DEMO_URL || 'http://127.0.0.1:3049';
assert.equal(new URL(base).hostname, '127.0.0.1');
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] });
const report = { schema_version: '1', status: 'insufficient_evidence', checked_rule_ids: [], policy_snapshots: [], findings: [], limitations: ['Synthetic fixture: no policies configured.'] };
const run = {
  run_id: 'demo-ui-review', intent: 'Order delivery question', status: 'partial', created_at: new Date().toISOString(), duration_seconds: 68,
  sentiment: null, outcome: null, quality_score: null, truth_score: null, confidence: null, cost_usd: null,
  provider: null, model: null, word_count: 15, hallucination_detected: 0, escalation_signal: 0,
  layer_scores: null, hallucination_evidence: null, policy_evidence: null, transcript_preview: null,
  transcript_speakers: [
    { speaker: 0, role: 'customer', role_source: 'transcript_label', text: 'Where is my order?' },
    { speaker: 1, role: 'agent', role_source: 'transcript_label', text: 'I can help you check the tracking.' },
  ],
  evaluation: { reliability: report, source_call: { platform: 'bolna', call_id: 'synthetic-execution' }, errors: ['Synthetic processing error'] },
};
const state = {
  review: null, reference: null, bolna: { source: 'bolna', scope: 'unknown', segments: [], audio_sha256: null, human_verified: false, verified_by: null },
  audio: { available: false, sha256: null, channels: null, duration_seconds: null, scope: 'unknown', scope_basis: 'Not confirmed' },
  provider: { name: 'deepgram', configured: false, requires_consent: false },
};
// A valid two-second silent WAV for browser decoding; not a real call recording.
const wav = Buffer.alloc(44 + 16000 * 2 * 2);
wav.write('RIFF'); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8);
wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
wav.writeUInt32LE(16000, 24); wav.writeUInt32LE(32000, 28); wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34);
wav.write('data', 36); wav.writeUInt32LE(wav.length - 44, 40);
let referenceUploads = 0, recordingLoads = 0, uploads = 0, failState = false, failAudio = false, failRetrieval = false, missingAudio = true, brokenStream = false;
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, httpCredentials: process.env.OPERATOR_AUTH_USER && process.env.OPERATOR_AUTH_PASSWORD
    ? { username: process.env.OPERATOR_AUTH_USER, password: process.env.OPERATOR_AUTH_PASSWORD } : undefined });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    const json = value => route.fulfill({ contentType: 'application/json', body: JSON.stringify(value) });
    if (path.endsWith('/analyze/stream')) {
      uploads++;
      const events = [{ event: 'started', run_id: run.run_id }, { event: 'complete', result: { run_id: run.run_id, status: 'partial' } }];
      return route.fulfill({ contentType: 'text/event-stream', body: brokenStream ? '' : events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('') });
    }
    if (path.endsWith('/stt-review/reference')) { referenceUploads++; return route.fulfill({ status: 500 }); }
    if (path.endsWith('/stt-review/recording')) {
      recordingLoads++;
      if (failRetrieval) return route.fulfill({ status: 503 });
      state.audio.available = !missingAudio;
      return json(state);
    }
    if (path.endsWith('/stt-review/audio')) return route.fulfill({ status: failAudio ? 404 : 200, contentType: 'audio/wav', body: failAudio ? '' : wav });
    if (path.endsWith('/stt-review')) return failState ? route.fulfill({ status: 403 }) : json(state);
    if (path.endsWith(`/runs/${run.run_id}`)) return json(run);
    if (path.endsWith('/runs')) return json({ runs: [run], total: 1, limit: 50, offset: 0 });
    if (path.endsWith('/health')) return json({ status: 'ok' });
    throw new Error(`Unexpected API path: ${path}`);
  });
  const open = async () => {
    await page.goto(`${base}/runs`);
    await page.getByRole('button', { name: `Review ${run.intent}`, exact: true }).click();
    await page.getByRole('region', { name: 'Call assessment' }).waitFor();
    assert.equal(await page.getByRole('tab', { name: 'Findings', exact: true }).getAttribute('aria-selected'), 'true');
    assert.deepEqual(await page.getByRole('tab').allTextContents(), ['Findings', 'Transcript', 'Speech diagnostics', 'STT quality', 'Evaluation checks']);
    assert.equal(await page.getByRole('region', { name: 'Call assessment' }).count(), 1);
    assert.equal(await page.locator('.call-debug').count(), 0);
    await page.getByRole('tab', { name: 'Transcript', exact: true }).click();
    await page.getByRole('list', { name: 'Call conversation' }).waitFor();
  };
  await open();
  assert.equal(await page.getByRole('link', { name: 'Calls', exact: true }).count(), 1);
  assert.equal(await page.getByRole('heading', { name: 'Calls', exact: true }).count(), 1);
  await page.getByRole('button', { name: 'Load recording', exact: true }).focus();
  await page.keyboard.press('Tab');
  assert.equal(await page.getByRole('button', { name: 'Close drawer', exact: true }).evaluate(element => element === document.activeElement), true);
  await page.keyboard.press('Shift+Tab');
  assert.equal(await page.getByRole('button', { name: 'Load recording', exact: true }).evaluate(element => element === document.activeElement), true);
  await page.getByRole('button', { name: 'Load recording', exact: true }).click();
  await page.getByText('The original recording could not be retrieved. It may have expired at the source.', { exact: true }).waitFor();
  missingAudio = false;
  await page.getByRole('button', { name: 'Retry recording', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.call-recording audio')?.duration === 2);
  await page.getByRole('tab', { name: 'Findings', exact: true }).click();
  await page.getByRole('heading', { name: 'No policy findings recorded' }).waitFor();
  assert.equal(await page.getByText('More evidence is needed', { exact: true }).count(), 0);
  await page.getByRole('tab', { name: 'Evaluation checks', exact: true }).click();
  await page.getByText('Synthetic processing error', { exact: true }).waitFor();
  await page.getByRole('heading', { name: 'Evaluator messages', exact: true }).waitFor();
  await page.getByRole('tab', { name: 'Speech diagnostics', exact: true }).click();
  await page.getByRole('heading', { name: 'Speech diagnostics unavailable', exact: true }).waitFor();
  await page.getByRole('tab', { name: 'STT quality', exact: true }).click();
  await page.getByRole('heading', { name: 'Post-call STT quality', exact: true }).waitFor();
  // A source recording can expire between loading metadata and requesting audio.
  failAudio = true;
  await page.getByRole('tab', { name: 'Transcript', exact: true }).click();
  await page.getByText('The recording is unavailable or has expired. Retrieve it again to retry.', { exact: true }).waitFor();
  failAudio = false;
  failRetrieval = true;
  await page.getByRole('button', { name: 'Retry recording', exact: true }).click();
  await page.getByText('Recording access is unavailable. Check access or try again.', { exact: true }).waitFor();
  failRetrieval = false;
  await page.getByRole('button', { name: 'Retry recording', exact: true }).click();
  await page.locator('.call-recording audio').waitFor();
  // An authenticated-proxy denial remains a quiet, actionable recording state.
  failState = true;
  await open();
  await page.getByText('Recording access is unavailable in this workspace.', { exact: true }).waitFor();
  failState = false;
  // Existing finding evidence must still jump to the original transcript turn.
  report.findings.push({ id: 'synthetic-claim', category: 'unverified_claim', status: 'needs_review', severity: 'medium', title: 'Synthetic finding', explanation: 'Fixture for navigation only.', evidence: [{ turn_index: 1, speaker_role: 'agent', role_source: 'transcript_label', quote: 'I can help you check the tracking.' }], policy_id: null, missing_evidence: ['tool_result'] });
  await open();
  await page.getByRole('tab', { name: 'Findings', exact: true }).click();
  await page.getByRole('button', { name: /Turn 2/ }).click();
  await page.locator('[data-turn-index="1"].turn-highlighted').waitFor();
  report.findings.length = 0;
  await open();
  await mkdir('../.gstack/calls-ui', { recursive: true });
  await page.screenshot({ path: '../.gstack/calls-ui/desktop.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.ok(await page.locator('.review-drawer').evaluate(element => element.scrollWidth <= element.clientWidth));
  await page.getByRole('tab', { name: 'Findings', exact: true }).click();
  assert.ok(await page.locator('.call-summary > div').evaluate(element => element.clientWidth >= 250), 'Mobile summary text must have room to read beside the icon');
  await page.getByRole('tab', { name: 'Transcript', exact: true }).click();
  await page.screenshot({ path: '../.gstack/calls-ui/mobile.png' });
  await page.keyboard.press('Escape');
  assert.equal(await page.getByRole('dialog').count(), 0);
  await page.getByRole('button', { name: `Review ${run.intent}`, exact: true }).waitFor({ state: 'attached' });
  assert.equal(await page.getByRole('button', { name: `Review ${run.intent}`, exact: true }).evaluate(element => element === document.activeElement), true);
  // A generated report must remain useful even when no company policies exist.
  run.provider = 'groq';
  run.evaluation.report = { executive_summary: 'Synthetic generated summary for a UI regression.' };
  run.evaluation.harness = { validation_passed: false, validation_errors: ['Synthetic analysis claim lacks transcript evidence'] };
  await open();
  await page.getByRole('tab', { name: 'Findings', exact: true }).click();
  await page.getByRole('region', { name: 'Generated call report' }).waitFor();
  await page.getByText('Synthetic generated summary for a UI regression.', { exact: true }).waitFor();
  await page.getByRole('heading', { name: '1 evaluation warning', exact: true }).waitFor();
  await page.getByRole('button', { name: 'View evaluation checks', exact: true }).click();
  assert.equal(await page.getByRole('tab', { name: 'Evaluation checks', exact: true }).getAttribute('aria-selected'), 'true');
  await page.getByText('Synthetic analysis claim lacks transcript evidence', { exact: true }).waitFor();
  await page.keyboard.press('Escape');
  await page.locator('#file-input').setInputFiles({ name: 'synthetic-ui.wav', mimeType: 'audio/wav', buffer: wav });
  await page.getByRole('dialog').waitFor();
  await page.waitForFunction(() => document.querySelector('.review-upload')?.getAttribute('aria-disabled') === 'false');
  assert.equal(await page.locator('.upload-progress').count(), 0, 'Finished upload stages must not clutter the list');
  await page.keyboard.press('Escape');
  brokenStream = true;
  await page.locator('#file-input').setInputFiles({ name: 'synthetic-ui.wav', mimeType: 'audio/wav', buffer: wav });
  await page.getByRole('alert').filter({ hasText: 'Analysis stream ended before a result was returned.' }).waitFor();
  assert.equal(await page.getByRole('dialog').count(), 0);
  // Next.js also owns an empty global route-announcer alert; count product errors.
  assert.equal(await page.locator('.calls-page').getByRole('alert').count(), 1, 'Upload errors must remain visible exactly once');
  assert.equal(uploads, 2);
  assert.equal(referenceUploads, 0);
  assert.equal(recordingLoads, 4);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ syntheticFixture: true, defaultFindings: true, tabs: 5, visibleEvaluationChecks: true, generatedReportAndWarningsVisible: true, audioLoadAndRetry: true, privateAccessError: true, evidenceNavigation: true, mobileOverflow: false, escapeRestoresFocus: true, uploadFlowPreserved: true, emptyStreamErrorVisible: true, referenceUploads, pageErrors: errors.length }));
} finally {
  await browser.close();
}
