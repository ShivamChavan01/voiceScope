// Read-only acceptance against operator-authorized, already prepared QA calls.
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';

const base = process.env.VOICESCOPE_BASE_URL;
assert.ok(base, 'Set VOICESCOPE_BASE_URL to the authorized staging or local build');
assert.ok(process.env.ALIGNMENT_RESULTS_FILE, 'Set ALIGNMENT_RESULTS_FILE to the prepared QA results');
const { calls } = JSON.parse(await readFile(process.env.ALIGNMENT_RESULTS_FILE, 'utf8'));
assert.ok(Array.isArray(calls) && calls.length > 0);
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({
  executablePath: process.env.BROWSER_EXE || '/usr/bin/google-chrome',
  args: ['--no-sandbox'],
});
const errors = [];
const checked = [];
let writes = 0;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (new URL(request.url()).origin === new URL(base).origin && !['GET', 'HEAD', 'OPTIONS'].includes(request.method())) writes++;
  });
  for (const call of calls) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`${base}/runs?call=${encodeURIComponent(call.call_id)}`);
    await page.getByRole('tab', { name: 'STT quality', exact: true }).click();
    const percentage = `${(call.metric_value * 100).toFixed(1)}%`;
    await page.getByRole('heading', { name: percentage, exact: true }).waitFor();
    const title = page.getByText('Automatic whole-call alignment', { exact: true });
    await title.waitFor();
    assert.equal(await page.getByText('Confirmed STT error', { exact: true }).count(), 0);
    assert.equal(await page.locator('input[type=file]').count(), 0);
    const response = await context.request.get(`${base}/api/v1/runs/${encodeURIComponent(call.call_id)}/stt-review`);
    assert.equal(response.status(), 200);
    const data = await response.json();
    assert.equal(data.review.metric_kind, 'estimated_disagreement');
    assert.equal(data.review.reference_human_verified, false);
    assert.ok(data.review.findings.every(finding => finding.status === 'needs_review'));
    assert.ok(data.bolna.segments.every(segment => segment.start === null));
    assert.ok(data.reference.segments.every(segment => segment.role === 'unknown'));
    const seekable = data.review.findings.filter(finding => finding.start !== null);
    const index = seekable.findIndex(finding => finding.start > 3 && finding.end < data.audio.duration_seconds - 1);
    assert.ok(index >= 0);
    for (let repeat = 0; repeat < 2; repeat++) {
      await page.getByRole('button', { name: /^Listen near / }).nth(index).click();
      await page.waitForFunction(time => {
        const audio = document.querySelector('.stt-audio audio');
        return audio && !audio.seeking && audio.currentTime >= time - .2 && audio.currentTime < time + 2;
      }, seekable[index].start);
      await page.locator('.stt-audio audio').evaluate(audio => audio.pause());
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await title.scrollIntoViewIfNeeded();
    const titleBox = await title.boundingBox();
    const paragraphs = title.locator('xpath=..').locator('p');
    const first = await paragraphs.nth(0).boundingBox();
    const second = await paragraphs.nth(1).boundingBox();
    assert.ok(titleBox && first && second);
    assert.ok(first.y >= titleBox.y + titleBox.height - 1, 'Mobile inference text must stack below the title, not form narrow columns');
    assert.ok(second.y >= first.y + first.height - 1, 'Mobile inference paragraphs must stack');
    const evidence = process.env.EVIDENCE_DIR;
    if (evidence) {
      await mkdir(evidence, { recursive: true, mode: 0o700 });
      await page.screenshot({ path: `${evidence}/${call.scenario}-mobile.png`, fullPage: true });
    }
    await page.reload();
    await page.getByRole('tab', { name: 'STT quality', exact: true }).click();
    await page.getByRole('heading', { name: percentage, exact: true }).waitFor();
    checked.push({ scenario: call.scenario, percentage, repeated_seek: true, reload: true, mobile_note_stacked: true });
  }
  assert.deepEqual(errors, []);
  assert.equal(writes, 0, 'Public viewing must not submit paid or modifying requests');
  if (process.env.EVIDENCE_DIR) {
    await writeFile(`${process.env.EVIDENCE_DIR}/results.json`, JSON.stringify({ checked, errors, writes }, null, 2), { mode: 0o600 });
  }
  console.log(JSON.stringify({ calls: checked.length, mobile_note_stacked: true, repeated_seek: true, reload: true, pageErrors: 0, public_writes: 0 }));
  await context.close();
} finally {
  await browser.close();
}
