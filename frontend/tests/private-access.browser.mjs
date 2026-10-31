// Opt-in production-mode access check. Uses only the private loopback review server.
import assert from 'node:assert/strict';

const base = process.env.STT_DEMO_URL || 'http://127.0.0.1:3069';
assert.equal(new URL(base).hostname, '127.0.0.1');
assert.ok(process.env.OPERATOR_AUTH_USER && process.env.OPERATOR_AUTH_PASSWORD);
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] });
try {
  const visitor = await browser.newContext();
  for (const path of ['/', '/runs', '/settings', '/api/v1/runs', '/api/v1/knowledge', '/api/v1/policies/rules', '/api/v1/runs/private/stt-review/audio', '/api/v1/runs/private/%2573tt-review/audio']) {
    const response = await visitor.request.get(base + path, { headers: { 'x-middleware-subrequest': 'middleware:middleware:middleware:middleware:middleware' } });
    assert.equal(response.status(), 401, path);
    assert.equal(response.headers()['cache-control'], 'no-store');
  }
  const operator = await browser.newContext({ httpCredentials: {
    username: process.env.OPERATOR_AUTH_USER, password: process.env.OPERATOR_AUTH_PASSWORD,
  } });
  const page = await operator.newPage();
  const errors = [];
  const fonts = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (new URL(response.url()).pathname.endsWith('.woff2')) fonts.push(response.status());
  });
  await page.goto(base + '/runs');
  await page.getByRole('heading', { name: 'Calls', exact: true }).waitFor();
  await page.evaluate(() => document.fonts.ready);
  assert.ok(fonts.length > 0, 'Exercise actual protected font requests');
  assert.ok(fonts.every(status => status === 200), 'Same-origin fonts must not be denied');
  // Browser fetch supplies the real Origin, unlike APIRequestContext by default.
  const mutation = await page.evaluate(async () => {
    const id = `qa-browser-${crypto.randomUUID()}`;
    const created = await fetch('/api/v1/policies/rules', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, title: 'Synthetic private browser regression',
        kind: 'no_same_day_refund_guarantee', text: 'Agents must never guarantee same-day refunds.', enabled: false }),
    });
    const removed = created.ok ? await fetch(`/api/v1/policies/rules/${id}`, { method: 'DELETE' }) : null;
    return { created: created.status, removed: removed?.status };
  });
  assert.deepEqual(mutation, { created: 200, removed: 200 });
  const protectedPage = await operator.request.get(base + '/runs');
  assert.equal(protectedPage.headers()['x-frame-options'], 'DENY');
  await page.route('https://synthetic-operator-link.example/', route => route.fulfill({ contentType: 'text/html', body: `<a href="${base}/runs">Private VoiceScope</a>` }));
  await page.goto('https://synthetic-operator-link.example/');
  await page.getByRole('link', { name: 'Private VoiceScope' }).click();
  await page.getByRole('heading', { name: 'Calls', exact: true }).waitFor();
  const asset = await page.locator('script[src]').first().getAttribute('src');
  assert.ok(asset?.startsWith('/_next/'));
  assert.equal((await visitor.request.get(base + asset)).status(), 401);
  const runs = await operator.request.get(base + '/api/v1/runs');
  assert.equal(runs.status(), 200);
  assert.equal(runs.headers()['cache-control'], 'no-store');
  const crossOrigin = await operator.request.get(base + '/api/v1/runs', { headers: { origin: 'https://synthetic-attacker.example' } });
  assert.equal(crossOrigin.status(), 403);
  assert.ok(process.env.STT_DISABLED_URL && process.env.STT_DEMO_RUN);
  assert.equal(new URL(process.env.STT_DISABLED_URL).hostname, '127.0.0.1');
  for (const segment of ['stt-review', '%73tt-review', '%2573tt-review']) {
    const disabled = await operator.request.get(`${process.env.STT_DISABLED_URL}/api/v1/runs/${encodeURIComponent(process.env.STT_DEMO_RUN)}/${segment}/audio`);
    assert.equal(disabled.status(), 403, segment);
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ unauthenticatedPathsDenied: 8, staticAssetProtected: true, middlewareHeaderBypassBlocked: true, operatorPageAndApi: true, operatorLinkNavigation: true, framingDenied: true, privateCacheControl: true, crossOriginBlocked: true, disabledSttEncodedPathsDenied: 3, pageErrors: 0 }));
} finally {
  await browser.close();
}
