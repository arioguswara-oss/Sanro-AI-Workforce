import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

const artifactDir = process.env.SANRO_CHROMIUM_EVIDENCE_DIR || path.join(os.tmpdir(), 'sanro-chromium-recovery');
const html = path.join(os.tmpdir(), `sanro-chromium-recovery-${process.pid}.html`);
const screenshot = path.join(artifactDir, 'synthetic-chromium-sandbox.png');
let browser;

try {
  fs.mkdirSync(artifactDir, { recursive: true, mode: 0o700 });
  fs.writeFileSync(html, '<!doctype html><meta charset="utf-8"><title>SANRO QA synthetic</title><main><button id="run">Run</button><output id="result">pending</output></main><script>document.querySelector("#run").onclick=()=>document.querySelector("#result").textContent="SANRO_CHROMIUM_SANDBOX_OK:"+(19*23)</script>');
  browser = await chromium.launch({ headless: true, chromiumSandbox: true });
  const page = await browser.newPage({ viewport: { width: 800, height: 450 } });
  await page.goto(pathToFileURL(html).href);
  await page.getByRole('button', { name: 'Run' }).click();
  const result = await page.locator('#result').textContent();
  if (result !== 'SANRO_CHROMIUM_SANDBOX_OK:437') throw new Error('synthetic DOM/JavaScript assertion failed');
  await page.screenshot({ path: screenshot });
  const digest = await import('node:crypto').then(({ createHash }) => createHash('sha256').update(fs.readFileSync(screenshot)).digest('hex'));
  await page.goto('chrome://sandbox');
  const sandboxDiagnostics = (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 1200);
  if (!/namespace sandbox/i.test(sandboxDiagnostics)) throw new Error('Chromium sandbox diagnostics did not report namespace sandbox status');
  console.log(JSON.stringify({ status: 'PASS', browserVersion: browser.version(), chromiumSandbox: true, customNoSandboxArgument: false, sandboxDiagnostics, result, screenshot, screenshotSha256: digest }));
} catch (error) {
  const message = String(error?.message || 'Chromium acceptance failed').split('\n')[0].slice(0, 240);
  console.log(JSON.stringify({ status: 'FAIL', chromiumSandbox: true, error: message }));
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  try { fs.unlinkSync(html); } catch {}
}
