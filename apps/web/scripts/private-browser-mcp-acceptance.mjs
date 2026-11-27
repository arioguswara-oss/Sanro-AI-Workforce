import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import http from 'node:http';
import net from 'node:net';
import { spawn, spawnSync } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { buildPrivateBrowserRuntimeConfig, TRUSTED_CHROMIUM_EXECUTABLE } from './private-browser-runtime-config.mjs';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const webRoot = path.join(repoRoot, 'apps/web');
const mcpBin = path.join(webRoot, 'node_modules/.bin/playwright-mcp');
const config = path.join(webRoot, 'playwright-mcp.config.json');
const stateRoot = process.env.SANRO_BROWSER_STATE_ROOT || path.join(process.env.TMPDIR || os.tmpdir(), 'sanro-private-browser-acceptance');
fs.mkdirSync(stateRoot, { recursive: true, mode: 0o700 });
const stateStat = fs.lstatSync(stateRoot);
if (stateStat.isSymbolicLink() || !stateStat.isDirectory() || stateStat.uid !== process.getuid() || (stateStat.mode & 0o077) !== 0) {
  throw new Error('Private browser state directory must be an owned, non-symlink directory with mode 0700');
}
async function assertTcpBlocked(host, port) {
  await new Promise((resolve, reject) => {
    const socket = net.createConnection({ host, port });
    const timer = setTimeout(() => { socket.destroy(); reject(new Error(`Unauthorized network target was not rejected: ${host}`)); }, 1000);
    socket.once('connect', () => { clearTimeout(timer); socket.destroy(); reject(new Error(`Unauthorized network target was reachable: ${host}`)); });
    socket.once('error', error => {
      clearTimeout(timer);
      if (['ENETUNREACH', 'EHOSTUNREACH', 'ENETDOWN', 'ECONNREFUSED'].includes(error.code)) resolve();
      else reject(new Error(`Unexpected network isolation probe result: ${error.code || 'unknown'}`));
    });
  });
}
async function verifyJobBoundary() {
  const ownNetns = fs.readlinkSync('/proc/self/ns/net');
  const initNetns = fs.readlinkSync('/proc/1/ns/net');
  if (ownNetns === initNetns) throw new Error('PrivateNetwork namespace is not active; direct runner invocation is refused');
  const interfaces = fs.readdirSync('/sys/class/net');
  if (interfaces.length !== 1 || interfaces[0] !== 'lo') throw new Error('Network namespace exposes a non-loopback interface');
  const cgroupLine = fs.readFileSync('/proc/self/cgroup', 'utf8').split('\n').find(line => line.startsWith('0::/'));
  if (!cgroupLine) throw new Error('Unified cgroup v2 job boundary is unavailable');
  const cgroupDir = path.join('/sys/fs/cgroup', cgroupLine.slice(3));
  const memoryMax = Number(fs.readFileSync(path.join(cgroupDir, 'memory.max'), 'utf8').trim());
  const [quotaText, periodText] = fs.readFileSync(path.join(cgroupDir, 'cpu.max'), 'utf8').trim().split(/\s+/);
  const pidsMax = Number(fs.readFileSync(path.join(cgroupDir, 'pids.max'), 'utf8').trim());
  const cpuQuota = quotaText === 'max' ? Infinity : Number(quotaText) / Number(periodText);
  if (!(memoryMax > 0 && memoryMax <= 2 * 1024 ** 3) || !(cpuQuota > 0 && cpuQuota <= 1) || !(pidsMax > 0 && pidsMax <= 128)) {
    throw new Error('Per-job cgroup CPU, memory, or task limit is missing or exceeds policy');
  }
  const routes = fs.readFileSync('/proc/net/route', 'utf8').trim().split('\n').slice(1);
  if (routes.some(line => line.trim().split(/\s+/)[1] === '00000000')) throw new Error('Default network route is present in private browser namespace');
  await assertTcpBlocked('1.1.1.1', 80);
  await assertTcpBlocked('169.254.169.254', 80);
  await assertTcpBlocked('127.0.0.1', 22);
  return { networkIsolation: 'private-network-namespace', unauthorizedEgressBlocked: true,
    cgroupLimits: { memoryMaxBytes: memoryMax, cpuQuotaCores: cpuQuota, pidsMax } };
}
const jobBoundary = process.env.SANRO_REQUIRE_PRIVATE_NETNS === '1' ? await verifyJobBoundary() : null;
const projectId = process.env.SANRO_PROJECT_ID;
const jobId = process.env.SANRO_JOB_ID;
const supportedProjects = new Set(['sanro-ai-workforce', 'sanro-browser-qa']);
const pilotApprovalValid = projectId !== 'sanro-browser-qa'
  || process.env.SANRO_PILOT_APPROVAL_ID === 'SANRO-QA-PILOT-OPS-V1';
if (!supportedProjects.has(projectId) || !pilotApprovalValid
    || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(jobId || '')) {
  throw new Error('Project/job scope is invalid for the authorized SANRO synthetic browser acceptance');
}
const lockDir = path.join(stateRoot, '.active-browser-job');
try {
  fs.mkdirSync(lockDir, { mode: 0o700 });
  fs.writeFileSync(path.join(lockDir, 'lease.json'), JSON.stringify({ pid: process.pid, projectId, jobId }), { mode: 0o600, flag: 'wx' });
} catch {
  throw new Error('Another private browser job is active or a stale fail-closed lock requires host review');
}
process.once('exit', () => { try { fs.rmSync(lockDir, { recursive: true, force: true }); } catch {} });
const jobDir = fs.mkdtempSync(path.join(stateRoot, 'job-'));
fs.chmodSync(jobDir, 0o700);
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(webRoot, '.cache/playwright');
const requireFromWeb = createRequire(path.join(webRoot, 'package.json'));
const chromium = requireFromWeb('playwright').chromium;
const mcpPackage = JSON.parse(fs.readFileSync(path.join(webRoot, 'node_modules/@playwright/mcp/package.json'), 'utf8'));
const browserExecutable = process.env.SANRO_CHROMIUM_EXECUTABLE || '';
const configValue = JSON.parse(fs.readFileSync(config, 'utf8'));
const runtimeConfig = path.join(jobDir, 'playwright-mcp.config.json');
const hostFacts = {
  uid: process.getuid(), cpuCount: os.cpus().length, totalMemoryBytes: os.totalmem(), freeMemoryBytes: os.freemem(),
  kernel: os.release(), userNamespace: fs.existsSync('/proc/self/ns/user') ? fs.readlinkSync('/proc/self/ns/user') : 'unavailable',
  unprivilegedUsernsClone: fs.existsSync('/proc/sys/kernel/unprivileged_userns_clone') ? fs.readFileSync('/proc/sys/kernel/unprivileged_userns_clone', 'utf8').trim() : 'not-exposed',
  appArmorEnabled: fs.existsSync('/sys/module/apparmor/parameters/enabled') ? fs.readFileSync('/sys/module/apparmor/parameters/enabled', 'utf8').trim() : 'not-exposed',
  chromiumExecutable: browserExecutable, chromiumExecutableExists: fs.existsSync(browserExecutable), mcpVersion: mcpPackage.version,
  chromiumSandboxConfigured: configValue.browser?.launchOptions?.chromiumSandbox === true,
};

let mcp;
let fixture;
let sessionId;
let nextId = 1;
let mcpDiagnostic = '';
let peakRssBytes = 0;
let peakProcessCount = 0;
let sampledCpuTicks = 0;
let browserProcessObserved = false;
let trustedBrowserExecutableObserved = false;
let chromiumNoSandboxArgumentObserved = false;
const previousCpuTicks = new Map();
let samplingTimer;
const sample = Buffer.from('<!doctype html><meta charset="utf-8"><title>SANRO private browser synthetic</title><main><h1>Private browser acceptance</h1><label for="value">Synthetic value</label><input id="value"><button id="run">Run check</button><output id="result">pending</output><script>document.querySelector("#run").addEventListener("click",()=>{document.querySelector("#result").textContent="DOM_OK:"+document.querySelector("#value").value+":"+(6*7)})</script></main>');

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      server.removeListener('error', reject);
      resolve(server.address().port);
    });
  });
}

function closeServer(server) {
  return new Promise(resolve => server?.close(() => resolve()));
}

async function responseJson(response) {
  const type = response.headers.get('content-type') || '';
  const body = await response.text();
  if (!response.ok) throw new Error(`MCP HTTP ${response.status}: ${body.slice(0, 240)}`);
  if (type.includes('text/event-stream')) {
    const data = body.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n');
    return data ? JSON.parse(data) : null;
  }
  return body ? JSON.parse(body) : null;
}

async function rpc(method, params, notification = false) {
  const headers = { accept: 'application/json, text/event-stream', 'content-type': 'application/json' };
  if (sessionId) headers['mcp-session-id'] = sessionId;
  const id = notification ? undefined : nextId++;
  const body = { jsonrpc: '2.0', method, ...(id === undefined ? {} : { id }), ...(params === undefined ? {} : { params }) };
  const response = await fetch('http://127.0.0.1:' + mcpPort + '/mcp', {
    method: 'POST', headers, body: JSON.stringify(body), signal: AbortSignal.timeout(20000),
  });
  sessionId ||= response.headers.get('mcp-session-id');
  const result = await responseJson(response);
  if (result?.error) throw new Error(`MCP ${method} error ${result.error.code}: ${result.error.message}`);
  return result;
}

let mcpPort;
const tools = new Map();
async function callTool(name, args) {
  if (!tools.has(name)) throw new Error(`Required tool was not discovered: ${name}`);
  const result = await rpc('tools/call', { name, arguments: args });
  if (result?.result?.isError) throw new Error(`Tool ${name} failed: ${(result.result.content || []).map(c => c.text || '').join(' ').slice(0, 240)}`);
  return result?.result;
}

async function waitForMcp() {
  const until = Date.now() + 15000;
  while (Date.now() < until) {
    if (mcp.exitCode !== null) throw new Error(`Playwright MCP exited during startup (${mcp.exitCode})`);
    try {
      const result = await rpc('initialize', {
        protocolVersion: '2025-03-26', capabilities: {},
        clientInfo: { name: 'sanro-private-browser-acceptance', version: '1.0.0' },
      });
      if (!result?.result?.serverInfo?.name) throw new Error('MCP initialize response lacked server identity');
      return result.result;
    } catch (error) {
      if (/MCP HTTP 4\d\d|MCP HTTP 5\d\d|MCP initialize error/.test(error.message)) throw error;
      await delay(200);
    }
  }
  throw new Error('Timed out waiting for Playwright MCP initialize');
}

function sampleProcessTree() {
  if (!mcp?.pid) return;
  try {
    const entries = fs.readdirSync('/proc').filter(name => /^\d+$/.test(name));
    const processes = new Map();
    for (const pid of entries) {
      try {
        const statLine = fs.readFileSync(`/proc/${pid}/stat`, 'utf8');
        const close = statLine.lastIndexOf(')');
        const fields = statLine.slice(close + 2).trim().split(/\s+/);
        processes.set(Number(pid), { ppid: Number(fields[1]), ticks: Number(fields[11]) + Number(fields[12]) });
      } catch {}
    }
    const selected = new Set([mcp.pid]);
    let changed = true;
    while (changed) {
      changed = false;
      for (const [pid, info] of processes) {
        if (!selected.has(pid) && selected.has(info.ppid)) { selected.add(pid); changed = true; }
      }
    }
    let rss = 0;
    for (const pid of selected) {
      const info = processes.get(pid);
      if (!info) continue;
      const previous = previousCpuTicks.get(pid) || 0;
      sampledCpuTicks += Math.max(0, info.ticks - previous);
      previousCpuTicks.set(pid, info.ticks);
      try {
        const line = fs.readFileSync(`/proc/${pid}/status`, 'utf8').split('\n').find(row => row.startsWith('VmRSS:'));
        rss += Number(line?.match(/\d+/)?.[0] || 0) * 1024;
      } catch {}
      try {
        const commandLine = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8').replaceAll('\0', ' ');
        if (/chrome|chromium/i.test(commandLine)) browserProcessObserved = true;
        if (commandLine.includes(TRUSTED_CHROMIUM_EXECUTABLE)) trustedBrowserExecutableObserved = true;
        if (/(^|\s)--no-sandbox(?:\s|$)/.test(commandLine)) chromiumNoSandboxArgumentObserved = true;
      } catch {}
    }
    peakRssBytes = Math.max(peakRssBytes, rss);
    peakProcessCount = Math.max(peakProcessCount, selected.size);
  } catch {}
}

const fixtureUrl = await new Promise((resolve, reject) => {
  fixture = http.createServer((request, response) => {
    if (request.method !== 'GET' || request.url !== '/') {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'content-length': sample.length, 'cache-control': 'no-store' });
    response.end(sample);
  });
  fixture.once('error', reject);
  fixture.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${fixture.address().port}/`));
});
const socket = http.createServer();
await listen(socket);
mcpPort = socket.address().port;
await closeServer(socket);

let result;
try {
  if (!fs.existsSync(mcpBin) || !fs.existsSync(config)) throw new Error('Pinned Playwright MCP executable or project config is missing');
  if (process.getuid() === 0) throw new Error('Browser runtime must not run as root');
  if (browserExecutable !== TRUSTED_CHROMIUM_EXECUTABLE || !path.isAbsolute(browserExecutable)
      || fs.realpathSync(browserExecutable) !== TRUSTED_CHROMIUM_EXECUTABLE) {
    throw new Error('Only the fixed approved root-owned Chromium executable is permitted');
  }
  let pathPart = browserExecutable;
  while (pathPart !== path.dirname(pathPart)) {
    const info = fs.statSync(pathPart);
    if (info.uid !== 0 || (info.mode & 0o022) !== 0) throw new Error('Approved Chromium path must remain root-owned and non-writable by group/other');
    pathPart = path.dirname(pathPart);
  }
  const executableInfo = fs.statSync(browserExecutable);
  if (!executableInfo.isFile() || (executableInfo.mode & 0o111) === 0) throw new Error('Approved Chromium executable is unavailable');
  if (mcpPackage.version !== '0.0.86' || configValue.browser?.launchOptions?.chromiumSandbox !== true || !hostFacts.chromiumExecutableExists) {
    throw new Error('Pinned MCP, Chromium executable, or chromiumSandbox=true preflight failed');
  }
  const ldd = spawnSync('/usr/bin/ldd', [browserExecutable], { encoding: 'utf8', timeout: 5000 });
  if (ldd.status !== 0 || /not found/.test(ldd.stdout || '')) throw new Error('Chromium shared-library preflight failed');
  const runtimeConfigValue = buildPrivateBrowserRuntimeConfig(configValue, browserExecutable);
  fs.writeFileSync(runtimeConfig, JSON.stringify(runtimeConfigValue), { mode: 0o600, flag: 'wx' });
  console.log(JSON.stringify({ status: 'PREFLIGHT', host: hostFacts, browserLibraries: 'resolved' }));
  mcp = spawn(mcpBin, [
    '--config', runtimeConfig, '--browser', 'chromium', '--headless', '--host', '127.0.0.1',
    '--port', String(mcpPort), '--allowed-hosts', '127.0.0.1,localhost',
    '--allowed-origins', new URL(fixtureUrl).origin, '--output-dir', jobDir,
    '--idle-timeout', '120000',
  ], { cwd: repoRoot, env: { PATH: '/usr/bin:/bin', LANG: 'C.UTF-8', HOME: jobDir, TMPDIR: jobDir, PLAYWRIGHT_BROWSERS_PATH: process.env.PLAYWRIGHT_BROWSERS_PATH }, stdio: ['ignore', 'ignore', 'pipe'], detached: true });
  let stderr = '';
  mcp.stderr.setEncoding('utf8');
  mcp.stderr.on('data', chunk => { stderr = (stderr + chunk).slice(-4000); mcpDiagnostic = stderr; });
  samplingTimer = setInterval(sampleProcessTree, 100);

  const serverInfo = await waitForMcp();
  await rpc('notifications/initialized', {}, true);
  const listing = await rpc('tools/list');
  for (const tool of listing?.result?.tools || []) tools.set(tool.name, tool);
  const required = ['browser_navigate', 'browser_snapshot', 'browser_click', 'browser_fill_form', 'browser_evaluate', 'browser_take_screenshot', 'browser_close'];
  if (required.some(name => !tools.has(name))) throw new Error('The MCP tools/list result did not contain the project allowlist');

  await callTool('browser_navigate', { url: fixtureUrl });
  const initialSnapshot = await callTool('browser_snapshot', {});
  if (!JSON.stringify(initialSnapshot).includes('Private browser acceptance')) throw new Error('DOM snapshot did not show the synthetic page title');
  await callTool('browser_fill_form', { fields: [{ name: 'Synthetic value', type: 'textbox', target: '#value', value: 'MCP_OK' }] });
  await callTool('browser_click', { target: '#run', element: 'synthetic Run check button' });
  const state = await callTool('browser_evaluate', { function: "() => document.querySelector('#result').textContent" });
  if (!JSON.stringify(state).includes('DOM_OK:MCP_OK:42')) throw new Error('JavaScript state assertion failed');
  const agent = await callTool('browser_evaluate', { function: '() => navigator.userAgent' });
  const userAgent = JSON.stringify(agent);
  const browserVersion = userAgent.match(/Chrome\/([0-9.]+)/)?.[1];
  if (!browserVersion) throw new Error('Chromium version was not present in the browser user agent');
  const screenshot = await callTool('browser_take_screenshot', { scale: 'css', type: 'png' });
  const image = screenshot?.content?.find(item => item.type === 'image' && item.mimeType === 'image/png');
  if (!image?.data) throw new Error('MCP screenshot returned no PNG image content');
  const screenshotPath = path.join(jobDir, 'acceptance.png');
  const bytes = Buffer.from(image.data, 'base64');
  if (bytes.length < 100 || bytes.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw new Error('MCP screenshot was not a valid PNG');
  fs.writeFileSync(screenshotPath, bytes, { mode: 0o600, flag: 'wx' });
  const digest = crypto.createHash('sha256').update(bytes).digest('hex');
  sampleProcessTree();
  if (!browserProcessObserved || !trustedBrowserExecutableObserved || chromiumNoSandboxArgumentObserved || hostFacts.uid === 0 || !hostFacts.chromiumSandboxConfigured) {
    throw new Error('Effective Chromium sandbox or non-root process verification failed');
  }
  await callTool('browser_close', {});
  result = {
    status: 'PASS', mcp: serverInfo.name, mcpVersion: serverInfo.version, browserVersion,
    browser: 'chromium', steps: ['initialize', 'tools/list', 'navigate', 'snapshot', 'fill', 'click', 'evaluate', 'screenshot', 'close'],
    javascriptState: 'DOM_OK:MCP_OK:42', screenshot: screenshotPath, screenshotSha256: digest,
    uid: hostFacts.uid, chromiumSandboxConfigured: hostFacts.chromiumSandboxConfigured,
    chromiumExecutable: TRUSTED_CHROMIUM_EXECUTABLE, trustedBrowserExecutableObserved, chromiumNoSandboxArgumentObserved,
    measured: { peakProcessTreeRssBytes: peakRssBytes, peakProcessCount, processTreeCpuTicks: sampledCpuTicks },
    networkIsolation: jobBoundary?.networkIsolation || 'NOT_ENFORCED', unauthorizedEgressBlocked: jobBoundary?.unauthorizedEgressBlocked === true,
    enforcedLimits: jobBoundary?.cgroupLimits || null,
    project: projectId, jobId, data: 'synthetic-only', listener: '127.0.0.1-only',
  };
} catch (error) {
  const lines = String(error?.stack || error).split('\n');
  const safe = mcpDiagnostic.split('\n').find(line => /No usable sandbox|sandboxing failed|Operation not permitted|SIGTRAP/.test(line))
    || lines.find(line => /Timed out|MCP HTTP|Required tool|assertion failed|exited during startup/.test(line)) || lines[0];
  result = { status: 'BLOCKED', project: projectId, jobId, error: safe.trim().slice(0, 240), diagnostic: (mcp?.exitCode !== null ? 'mcp_exited' : 'mcp_alive'), measured: { peakProcessTreeRssBytes: peakRssBytes, peakProcessCount, processTreeCpuTicks: sampledCpuTicks } };
  process.exitCode = 1;
} finally {
  clearInterval(samplingTimer);
  sampleProcessTree();
  let cleanup = 'PASS';
  if (mcp) {
    try { process.kill(-mcp.pid, 'SIGTERM'); } catch {}
    const cleanupUntil = Date.now() + 3000;
    while (Date.now() < cleanupUntil) {
      try { process.kill(-mcp.pid, 0); } catch { break; }
      await delay(100);
    }
    try {
      process.kill(-mcp.pid, 0);
      process.kill(-mcp.pid, 'SIGKILL');
    } catch {}
    const killUntil = Date.now() + 2000;
    while (Date.now() < killUntil) {
      try { process.kill(-mcp.pid, 0); } catch { break; }
      await delay(100);
    }
    try { process.kill(-mcp.pid, 0); cleanup = 'FAIL'; } catch {}
    if (mcp.exitCode === null) await Promise.race([new Promise(resolve => mcp.once('exit', resolve)), delay(1000)]);
  }
  await closeServer(fixture);
  if (result?.status !== 'PASS') fs.rmSync(jobDir, { recursive: true, force: true });
  fs.rmSync(lockDir, { recursive: true, force: true });
  if (result) result.cleanup = cleanup;
  if (cleanup !== 'PASS' && result) {
    result.status = 'BLOCKED';
    result.error = 'Playwright process group did not terminate cleanly';
    result.screenshot = null;
    fs.rmSync(jobDir, { recursive: true, force: true });
  }
}
console.log(JSON.stringify(result));
if (result?.cleanup !== 'PASS') process.exitCode = 1;
