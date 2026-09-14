import fs from 'node:fs';
import path from 'node:path';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const api = process.env.BANKPULSE_URL || 'http://localhost:18080';
const grafana = process.env.GRAFANA_URL || 'http://localhost:13000';
const out = process.env.EVIDENCE_DIR || 'artifacts/browser';
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const context = await browser.newContext({ viewport: { width: 1500, height: 1150 } });
const page = await context.newPage();
const errors = [];
const browserDiagnostics = { console: [], requests: [], websockets: [] };
let phase = 'console';
page.on('console', message => { if (message.type() === 'error') browserDiagnostics.console.push(message.text()); });
page.on('requestfailed', request => browserDiagnostics.requests.push({url:request.url(), error:request.failure()?.errorText}));
page.on('websocket', socket => { const item={url:socket.url(),frames:0,errors:[]}; browserDiagnostics.websockets.push(item); socket.on('framereceived',()=>item.frames++);socket.on('socketerror',error=>item.errors.push(error)); });
page.on('pageerror', error => errors.push(error.message));
try {
// Exercise the actual console before the isolated latency run. This also leaves
// a recent valid closure, so B-K1 has an unambiguous expected visible value.
await page.goto(api, { waitUntil: 'networkidle' });
await page.locator('[data-view="split"]').click();
await page.locator('#splitTotal').fill('100');
await page.locator('#splitPeople').selectOption('3');
await page.locator('#createSplit').click();
await page.waitForFunction(() => document.querySelectorAll('#splitParticipants .participant').length === 3);
const shares = await page.locator('#splitParticipants .amount').allTextContents();
if ([...shares].sort().join(',') !== '$33.33,$33.33,$33.34') throw new Error('UI failed exact cent allocation: ' + shares);
for (let n = 1; n <= 3; n++) {
  await page.locator('[data-authorize]:not([disabled])').first().click();
  await page.waitForFunction(expected => document.querySelectorAll('[data-authorize][disabled]').length === expected, n);
}
const closing = page.waitForResponse(r => r.url().includes('/api/splits/') && r.url().endsWith('/close') && r.request().method() === 'POST');
await page.locator('#closeSplit').click();
const closedResponse = await closing;
const closed = await closedResponse.json();
await page.waitForFunction(() => document.querySelector('#splitStatus')?.textContent === 'COMPLETED');
if (Number(closed.participants.find(p => p.memberId === 'MEMBER-001')?.shareAmount) !== 33.34) throw new Error('Remainder cent did not stay with the host');
if (!closedResponse.ok() || closed.status !== 'COMPLETED' || Number(closed.totalAmount) !== 100 || new Set(closed.participants.map(p => p.paymentReference)).size !== 3 || !(await page.locator('#closeSplit').isDisabled())) throw new Error('UI closure did not persist exact demo references');
fs.writeFileSync(path.join(out, 'console-split-100-three.json'), JSON.stringify({ shares, closed }, null, 2));
await page.waitForFunction(() => { const bar = document.querySelector('#splitProgressBar'); return Math.abs(bar.getBoundingClientRect().width - bar.parentElement.getBoundingClientRect().width) < 1; });
await page.screenshot({ path: path.join(out, 'console-split-100-three.png'), fullPage: true });
phase = 'grafana-bootstrap';
const login = await context.request.post(grafana + '/login', { data: { user: 'admin', password: process.env.GRAFANA_PASSWORD || 'bankpulse_demo' } });
if (!login.ok()) throw new Error('Grafana lab login failed: ' + login.status());
await page.goto(grafana + '/d/bankpulse-business', { waitUntil: 'networkidle' });
await page.locator('[data-bankpulse-panel="event_count"]').waitFor({ timeout: 30000 });
await page.waitForFunction(() => document.querySelector('[data-bankpulse-panel="event_count"]')?.dataset.quality === 'VIGENTE', { timeout: 30000 });
const samples = [];
const connectionEvidence = {};
async function connectionState() { return page.evaluate(() => ({observedAt: new Date().toISOString(), panels: Array.from(document.querySelectorAll('[data-bankpulse-panel]')).map(node => ({field:node.dataset.bankpulsePanel, revision:node.dataset.revision, eventId:node.dataset.eventId, quality:node.dataset.quality, value:node.firstElementChild?.textContent,computedAt:node.lastElementChild?.textContent}))})); }
const count = Number(process.env.LATENCY_SAMPLES || 100);
if (!Number.isInteger(count) || count < 100) throw new Error('Acceptance requires at least 100 samples');
const baseline = await (await context.request.get(api + '/api/business/snapshot')).json();
const sourceBaseline = await (await context.request.get(api + '/api/splits/outbox-status')).json();
if (!baseline.coverage.complete || sourceBaseline.pending !== 0 || sourceBaseline.versionSum !== baseline.coverage.eventCount) {
  throw new Error('Benchmark requires a complete, drained and independently counted source baseline');
}
const expectedIntegrity = baseline.kpis.USD?.['B-K1']?.value;
const businessText = expectedIntegrity == null ? 'SIN MUESTRA' : Number(expectedIntegrity).toLocaleString('es-EC', { maximumFractionDigits: 2 });
// Both cards must paint the same correlated revision. Read again at t1 after RAF.
function readRendered({ eventId, expectedText, businessText }) {
  const technical = document.querySelector('[data-bankpulse-panel="event_count"]');
  const business = document.querySelector('[data-bankpulse-panel="integrity_percent"]');
  const read = node => node && ({ text: node.innerText, value: node.firstElementChild?.textContent.trim(), revision: node.dataset.revision, quality: node.dataset.quality, eventId: node.dataset.eventId, computedAt: node.lastElementChild?.textContent });
  const counter = read(technical), kpi = read(business);
  return counter?.eventId === eventId && kpi?.eventId === eventId && counter.quality === 'VIGENTE' && kpi.quality === 'VIGENTE' && counter.revision === kpi.revision && counter.value === expectedText && kpi.value === businessText ? { counter, kpi } : null;
}
const run = 'browser-' + crypto.randomUUID();
try {
  phase = 'measurement';
  for (let i = 0; i < count; i++) {
    const start = await page.evaluate(() => performance.now());
    const response = await context.request.post(api + '/api/splits', { data: { hostMemberId: 'BROWSER-DEMO', totalAmount: 100, currency: 'USD', fixtureRunId: run } });
    const data = await response.json();
    if (!response.ok() || !data.lastEventId) { samples.push({ i, error: 'API failure', status: response.status(), data }); continue; }
    let end;
    try {
      const expectedCount = sourceBaseline.versionSum + i + 1;
      const expected = { eventId: data.lastEventId, expectedText: expectedCount.toLocaleString('es-EC', { maximumFractionDigits: 2 }), businessText };
      await page.waitForFunction(readRendered, expected, { timeout: 5000, polling: 'raf' });
      const finalFrame = await page.evaluate(async ({ expected, readSource }) => {
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const read = new Function('return (' + readSource + ')')();
        return { end: performance.now(), observedAt: new Date().toISOString(), rendered: read(expected) };
      }, { expected, readSource: readRendered.toString() });
      if (!finalFrame.rendered) throw new Error('Cards no longer match their source event and expected values at t1');
      end = finalFrame.end;
      samples.push({ i, aggregateId: data.id, eventId: data.lastEventId, expectedCount, expectedBusinessValue: businessText, rendered: finalFrame.rendered, observedAt: finalFrame.observedAt, start, end, milliseconds: end - start });
    } catch (error) { samples.push({ i, eventId: data.lastEventId, lost: true, error: error.message }); }
  }
  await page.waitForFunction(() => document.querySelector('[data-bankpulse-panel="event_count"]')?.dataset.quality === 'VIGENTE');
  connectionEvidence.connected = await connectionState();
  await page.screenshot({ path: path.join(out, 'grafana-live.png'), fullPage: true });
  // Client watchdog must invalidate a frozen data frame even if Grafana itself is connected.
  phase = 'disconnect';
  await context.setOffline(true);
  await page.waitForFunction(() => document.querySelector('[data-bankpulse-panel="event_count"]')?.dataset.quality === 'DESACTUALIZADO', { timeout: 7000 });
  connectionEvidence.disconnected = await connectionState();
  await page.screenshot({ path: path.join(out, 'grafana-disconnected.png'), fullPage: true });
  phase = 'reconnect';
  await context.setOffline(false);
  // Existing tab and subscription recover; no reload is used.
  await page.waitForFunction(() => document.querySelector('[data-bankpulse-panel="event_count"]')?.dataset.quality === 'VIGENTE', { timeout: 30000 });
  connectionEvidence.reconnected = await connectionState();
  if (Number(connectionEvidence.reconnected.panels[0].revision) <= Number(connectionEvidence.disconnected.panels[0].revision)) throw new Error('Reconnection did not advance its durable revision');
  await page.screenshot({ path: path.join(out, 'grafana-reconnected.png'), fullPage: true });
} finally {
  const values = samples.filter(x => Number.isFinite(x.milliseconds)).map(x => x.milliseconds).sort((a, b) => a - b);
  const percentile = q => values[Math.max(0, Math.ceil(q * values.length) - 1)] ?? null;
  const result = { fixtureRunId: run, connectionEvidence, browserDiagnostics, baseline, sourceBaseline, browserVersion: browser.version(), playwrightModule: process.env.PLAYWRIGHT_MODULE || "package-lock.json", requested: count, sent: samples.length, observed: values.length, lost: samples.filter(x => x.lost).length, errors: samples.filter(x => x.error).length, pageErrors: errors, p50: percentile(.5), p95: percentile(.95), maximum: values.at(-1), clock: 'performance.now() in the same Grafana page, before API dispatch to two animation frames after visible correlated FRESH render', samples };
  fs.writeFileSync(path.join(out, 'latency.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ ...result, samples: undefined }, null, 2));
  await browser.close();
  if (result.sent !== count || result.observed !== count || result.lost || result.errors || errors.length || result.p95 > 1000) process.exitCode = 1;
}

} catch (error) {
  const failure = { phase, error: error.message, stack: error.stack, url: page.url(), observedAt: new Date().toISOString(), pageErrors: errors, browserDiagnostics };
  if (!page.isClosed()) {
    failure.body = await page.locator('body').innerText().catch(() => 'unavailable');
    await page.screenshot({ path: path.join(out, 'failure.png'), fullPage: true }).catch(() => {});
    fs.writeFileSync(path.join(out, 'failure.html'), await page.content().catch(() => 'unavailable'));
  }
  fs.writeFileSync(path.join(out, 'failure.json'), JSON.stringify(failure, null, 2));
  await browser.close();
  throw error;
}
