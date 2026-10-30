// Opt-in real-service smoke check. Requires an already cached, authorized reference.
// PLAYWRIGHT_MODULE may point to an existing Playwright installation; no dependency install.
import assert from 'node:assert/strict';

const base = process.env.STT_DEMO_URL || 'http://127.0.0.1:3049';
const run = process.env.STT_DEMO_RUN;
assert.equal(new URL(base).hostname, '127.0.0.1', 'Use the private loopback demo');
assert.ok(run, 'Set STT_DEMO_RUN to the real imported run ID');
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH,
  args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'],
});
try {
  const page = await browser.newPage();
  const errors = [];
  let providerSubmissions = 0;
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/stt-review/reference')) providerSubmissions++;
  });
  const stateResponse = await page.request.get(`${base}/api/v1/runs/${encodeURIComponent(run)}/stt-review`);
  assert.equal(stateResponse.status(), 200);
  const state = await stateResponse.json();
  assert.ok(state.reference?.segments.length, 'Prepare the authorized reference before running this check');
  assert.equal(state.reference.human_verified, false);
  const open = async () => {
    await page.goto(`${base}/runs?call=${encodeURIComponent(run)}`);
    await page.getByRole('tab', { name: 'STT quality', exact: true }).click();
    await page.locator('.stt-transcript-panel').first().waitFor();
    assert.equal(await page.locator('.stt-transcript-panel').count(), 2);
    assert.equal(await page.locator('.stt-comparison-setup').first().getAttribute('open'), null);
    assert.equal(await page.locator('.stt-transcript-panel').first().locator('li').count(), state.bolna.segments.length);
    assert.equal(await page.locator('.stt-transcript-panel').nth(1).locator('li').count(), state.reference.segments.length);
  };
  await open();
  const audio = page.locator('.stt-audio audio');
  await page.waitForFunction(() => Number.isFinite(document.querySelector('.stt-audio audio')?.duration));
  const timed = state.reference.segments.findIndex(segment => segment.start > 10);
  assert.ok(timed >= 0, 'Need a real timestamp after 10 seconds for seeking');
  const start = state.reference.segments[timed].start;
  await page.locator('.stt-transcript-panel').nth(1).locator('li').nth(timed).getByRole('button').click();
  await page.waitForFunction(target => {
    const player = document.querySelector('.stt-audio audio');
    return !player.paused && player.currentTime >= target && player.currentTime < target + 3;
  }, start);
  await audio.evaluate(element => element.pause());
  await open();
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  // Controlled expiry response, after the real playback check above. No artifacts deleted.
  await page.route('**/stt-review/audio', route => route.fulfill({ status: 404 }));
  await open();
  await page.getByText('The private recording is unavailable or expired.', { exact: true }).waitFor();
  assert.equal(providerSubmissions, 0, 'Reload must reuse the cached reference');
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({
    realAudioPlayback: true, referenceTimestampSeek: true, reload: true,
    originalTurns: state.bolna.segments.length, independentSegments: state.reference.segments.length,
    providerSubmissions, pageErrors: errors.length, mobileOverflow: false,
    controlledExpiredAudioError: true,
    metric: state.review?.metric_value ?? null,
    findingNavigation: 'Not exercised: this real call has no aligned findings yet',
  }));
} finally {
  await browser.close();
}
