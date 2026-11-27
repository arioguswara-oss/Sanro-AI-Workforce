import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';
import { parseChromiumSandbox } from './chromium-sandbox-diagnostics.mjs';

const artifactDir = process.env.SANRO_CHROMIUM_EVIDENCE_DIR;
const html = path.join(os.tmpdir(), `sanro-chromium-recovery-${process.pid}.html`);
const executablePath = process.env.SANRO_CHROMIUM_EXECUTABLE;
const expectedBrowserVersion = '159.0.8154.6';
let browser;
let page;
let stage = 'preflight';
let result = { status: 'FAIL', chromiumSandboxRequested: true };

function record(name, status, details = {}) {
  const row = { at: new Date().toISOString(), stage: name, status, ...details };
  fs.appendFileSync(path.join(artifactDir, 'stages.jsonl'), `${JSON.stringify(row)}\n`, { mode: 0o600 });
  return row;
}

function saveJson(name, value) {
  fs.writeFileSync(path.join(artifactDir, name), `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600, flag: 'wx' });
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

try {
  if (!artifactDir || !path.isAbsolute(artifactDir)) throw new Error('SANRO_CHROMIUM_EVIDENCE_DIR must name a pre-created private evidence directory');
  const evidenceInfo = fs.lstatSync(artifactDir);
  if (!evidenceInfo.isDirectory() || evidenceInfo.isSymbolicLink() || fs.realpathSync(artifactDir) !== artifactDir || evidenceInfo.uid !== process.getuid() || (evidenceInfo.mode & 0o077) !== 0) {
    throw new Error('evidence directory must be canonical, non-symlink, owned by current user, and private (0700)');
  }
  record(stage, 'PASS', { evidenceDirectory: artifactDir });
  if (!executablePath || !path.isAbsolute(executablePath)) throw new Error('SANRO_CHROMIUM_EXECUTABLE must name the approved root-owned Chromium executable');
  const canonicalExecutable = fs.realpathSync(executablePath);
  if (canonicalExecutable !== executablePath) throw new Error('approved Chromium path must not resolve through a symlink');
  let pathPart = executablePath;
  while (pathPart !== path.dirname(pathPart)) {
    const metadata = fs.statSync(pathPart);
    if (metadata.uid !== 0 || (metadata.mode & 0o022) !== 0) throw new Error('approved Chromium path must be root-owned and not group/world writable');
    pathPart = path.dirname(pathPart);
  }
  const executableStat = fs.statSync(executablePath);
  if (!executableStat.isFile() || (executableStat.mode & 0o111) === 0) throw new Error('approved Chromium executable is missing execute permission');
  record(stage, 'PASS', { executablePath: canonicalExecutable, executableOwnerUid: executableStat.uid });

  stage = 'synthetic_page';
  fs.writeFileSync(html, '<!doctype html><meta charset="utf-8"><title>SANRO QA synthetic</title><main><button id="run">Run</button><output id="result">pending</output></main><script>document.querySelector("#run").onclick=()=>document.querySelector("#result").textContent="SANRO_CHROMIUM_SANDBOX_OK:"+(19*23)</script>', { mode: 0o600, flag: 'wx' });
  browser = await chromium.launch({ headless: true, chromiumSandbox: true, executablePath });
  result.browserVersion = browser.version();
  if (result.browserVersion !== expectedBrowserVersion) throw new Error(`unexpected Chromium version: ${result.browserVersion}`);
  page = await browser.newPage({ viewport: { width: 800, height: 450 } });
  await page.goto(pathToFileURL(html).href);
  await page.getByRole('button', { name: 'Run' }).click();
  result.syntheticResult = await page.locator('#result').textContent();
  if (result.syntheticResult !== 'SANRO_CHROMIUM_SANDBOX_OK:437') throw new Error('synthetic DOM/JavaScript assertion failed');
  result.syntheticScreenshot = path.join(artifactDir, 'synthetic-chromium-sandbox.png');
  await page.screenshot({ path: result.syntheticScreenshot });
  result.syntheticScreenshotSha256 = sha256(result.syntheticScreenshot);
  record(stage, 'PASS', { browserVersion: result.browserVersion, syntheticResult: result.syntheticResult, screenshot: result.syntheticScreenshot, screenshotSha256: result.syntheticScreenshotSha256 });

  stage = 'sandbox_diagnostics';
  let navigationError;
  try {
    await page.goto('chrome://sandbox', { waitUntil: 'domcontentloaded', timeout: 10000 });
  } catch (error) {
    navigationError = String(error?.stack || error);
  }
  let diagnostics;
  try {
    diagnostics = await page.evaluate(() => ({
      url: location.href,
      title: document.title,
      bodyText: document.body?.innerText ?? '',
      rows: [...document.querySelectorAll('tr')].map((row) => ({ cells: [...row.querySelectorAll('th,td')].map((cell) => cell.innerText.trim()) })),
      tableHtml: [...document.querySelectorAll('table')].map((table) => table.outerHTML),
      documentHtml: document.documentElement?.outerHTML ?? '',
    }));
  } catch (error) {
    diagnostics = { url: page.url(), captureError: String(error?.stack || error) };
  }
  if (navigationError) diagnostics.navigationError = navigationError;
  saveJson('sandbox-diagnostics.json', diagnostics);
  record(stage, 'CAPTURED', { rawDiagnostics: path.join(artifactDir, 'sandbox-diagnostics.json'), rawDiagnosticsSha256: sha256(path.join(artifactDir, 'sandbox-diagnostics.json')) });
  try {
    result.diagnosticsScreenshot = path.join(artifactDir, 'chrome-sandbox-diagnostics.png');
    await page.screenshot({ path: result.diagnosticsScreenshot, fullPage: true });
    result.diagnosticsScreenshotSha256 = sha256(result.diagnosticsScreenshot);
    record(stage, 'CAPTURED', { diagnosticsScreenshot: result.diagnosticsScreenshot, diagnosticsScreenshotSha256: result.diagnosticsScreenshotSha256 });
  } catch (error) {
    result.diagnosticsScreenshotError = String(error?.stack || error);
    record(stage, 'CAPTURE_FAILED', { diagnosticsScreenshotError: result.diagnosticsScreenshotError });
  }
  result.sandboxAssessment = parseChromiumSandbox(diagnostics);
  if (!result.sandboxAssessment.active) throw new Error(`Chromium mandatory sandbox controls not proven: ${result.sandboxAssessment.failures.join('; ')}`);
  record(stage, 'PASS', { sandboxAssessment: result.sandboxAssessment });
  result.status = 'PASS';
  result.chromiumSandbox = true;
} catch (error) {
  result.status = 'FAIL';
  result.failedStage = stage;
  result.error = String(error?.stack || error);
  try { record(stage, 'FAIL', { error: result.error }); } catch {}
} finally {
  if (browser) {
    try {
      await browser.close();
      result.browserCleanup = 'PASS';
      try { record('browser_cleanup', 'PASS'); } catch {}
    } catch (error) {
      result.browserCleanup = 'FAIL';
      result.browserCleanupError = String(error?.stack || error);
      result.status = 'FAIL';
      try { record('browser_cleanup', 'FAIL', { error: result.browserCleanupError }); } catch {}
    }
  } else result.browserCleanup = 'NOT_STARTED';
  try {
    fs.unlinkSync(html);
    result.syntheticPageCleanup = 'PASS';
  } catch (error) {
    result.syntheticPageCleanup = error?.code === 'ENOENT' ? 'PASS' : 'FAIL';
    if (result.syntheticPageCleanup === 'FAIL') result.syntheticPageCleanupError = String(error?.message || error);
  }
  if (artifactDir && path.isAbsolute(artifactDir)) {
    try { saveJson('result.json', result); } catch (error) {
      result.resultEvidenceWriteError = String(error?.stack || error);
      result.status = 'FAIL';
    }
  }
  console.log(JSON.stringify(result));
  if (result.status !== 'PASS') process.exitCode = 1;
}
