import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const html = path.join(os.tmpdir(), `sanro-gdi02r-browser-${process.pid}.html`);
const screenshot = path.join(repoRoot, 'apps/web/.cache/playwright/GDI02R_CHROMIUM_SMOKE.png');
let browser;

try {
  fs.writeFileSync(html, '<!doctype html><meta charset="utf-8"><title>GDI-02R synthetic</title><main><button id="run">Run local check</button><output id="result">pending</output></main><script>document.querySelector("#run").addEventListener("click",()=>{document.querySelector("#result").textContent="DOM_OK:"+(6*7)})</script>');
  browser = await chromium.launch({ headless: true, chromiumSandbox: true });
  const page = await browser.newPage({ viewport: { width: 800, height: 450 } });
  await page.goto(pathToFileURL(html).href);
  await page.getByRole('button', { name: 'Run local check' }).click();
  const result = await page.locator('#result').textContent();
  if (result !== 'DOM_OK:42') throw new Error('synthetic DOM and JavaScript assertion failed');
  fs.mkdirSync(path.dirname(screenshot), { recursive: true });
  await page.screenshot({ path: screenshot });
  console.log(JSON.stringify({ status: 'PASS', browserVersion: browser.version(), result, screenshot: 'apps/web/.cache/playwright/GDI02R_CHROMIUM_SMOKE.png' }));
} catch (error) {
  const diagnostic = String(error?.message ?? 'browser runtime failed');
  const denied = diagnostic.split('\n').find(line => /setsockopt|Operation not permitted|SIGTRAP|EPERM/.test(line));
  const safeError = denied ? denied.replace(/\/[^\s]+/g, '<path>').slice(0, 220) : diagnostic.split('\n')[0];
  console.log(JSON.stringify({ status: 'BLOCKED', error: safeError }));
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  try { fs.unlinkSync(html); } catch {}
}
