import test from 'node:test';
import assert from 'node:assert/strict';
import { parseChromiumSandbox } from '../scripts/chromium-sandbox-diagnostics.mjs';
import { buildPrivateBrowserRuntimeConfig, TRUSTED_CHROMIUM_EXECUTABLE } from '../scripts/private-browser-runtime-config.mjs';

const chromium159ActualRows = [
  ['Layer 1 Sandbox', 'Namespace'],
  ['PID namespaces', 'Yes'],
  ['Network namespaces', 'Yes'],
  ['Seccomp-BPF sandbox', 'Yes'],
  ['Seccomp-BPF sandbox supports TSYNC', 'Yes'],
  ['Ptrace Protection with Yama LSM (Broker)', 'Yes'],
  ['Ptrace Protection with Yama LSM (Non-broker)', 'No'],
];

test('accepts actual Chromium 159 diagnostics and warns on Yama Non-broker No', () => {
  const result = parseChromiumSandbox({ rows: chromium159ActualRows.map((cells) => ({ cells })) });
  assert.equal(result.status, 'PASS');
  assert.equal(result.active, true);
  for (const label of ['Layer 1 Sandbox', 'PID namespaces', 'Network namespaces', 'Seccomp-BPF sandbox', 'Seccomp-BPF sandbox supports TSYNC']) {
    assert.equal(result.checks[label].status, 'PASS', `${label} must be explicitly verified`);
  }
  assert.equal(result.checks['Yama Non-broker'].status, 'WARNING');
  assert.match(result.warnings.join('; '), /Yama Non-broker.*No/);
});

test('accepts explicit actual-format body text with tab-separated values', () => {
  const bodyText = chromium159ActualRows.map(([label, value]) => `${label}\t${value}`).join('\n');
  assert.equal(parseChromiumSandbox({ bodyText }).active, true);
});

test('fails closed if any mandatory sandbox control reports No', () => {
  for (const target of ['PID namespaces', 'Network namespaces', 'Seccomp-BPF sandbox', 'Seccomp-BPF sandbox supports TSYNC']) {
    const result = parseChromiumSandbox({ rows: chromium159ActualRows.map(([label, value]) => [label, label === target ? 'No' : value]) });
    assert.equal(result.active, false, `${target} No must fail`);
    assert.ok(result.failures.some((failure) => failure.startsWith(target)));
  }
  const noNamespace = chromium159ActualRows.map(([label, value]) => [label, label === 'Layer 1 Sandbox' ? 'None' : value]);
  assert.equal(parseChromiumSandbox({ rows: noNamespace }).active, false);
});

test('fails closed on missing, malformed, conflicting or legacy-only namespace evidence', () => {
  assert.equal(parseChromiumSandbox({}).active, false);
  assert.equal(parseChromiumSandbox({ rows: [['Layer 1 Sandbox', 'Namespace']] }).active, false);
  const conflicting = [...chromium159ActualRows, ['PID namespaces', 'No']];
  assert.equal(parseChromiumSandbox({ rows: conflicting }).active, false);
  assert.equal(parseChromiumSandbox({ rows: [['Namespace Sandbox', 'Yes']] }).active, false);
});

test('records Yama Non-broker absence as warning without hiding mandatory failures', () => {
  const rows = chromium159ActualRows.filter(([label]) => !label.includes('Non-broker'));
  const result = parseChromiumSandbox({ rows });
  assert.equal(result.active, true);
  assert.equal(result.checks['Yama Non-broker'].status, 'WARNING');
  assert.equal(parseChromiumSandbox({ rows: rows.map(([label, value]) => [label, label === 'Seccomp-BPF sandbox' ? 'No' : value]) }).active, false);
});

test('binds runtime Playwright MCP to the exact trusted executable with sandbox intact', () => {
  const source = { browser: { browserName: 'chromium', launchOptions: { headless: true, chromiumSandbox: true } } };
  const runtime = buildPrivateBrowserRuntimeConfig(source, TRUSTED_CHROMIUM_EXECUTABLE);
  assert.equal(runtime.browser.launchOptions.executablePath, TRUSTED_CHROMIUM_EXECUTABLE);
  assert.equal(runtime.browser.launchOptions.chromiumSandbox, true);
  assert.equal(source.browser.launchOptions.executablePath, undefined);
});

test('rejects missing or substituted browser executable and disabled sandbox without fallback', () => {
  const source = { browser: { browserName: 'chromium', launchOptions: { chromiumSandbox: true } } };
  assert.throws(() => buildPrivateBrowserRuntimeConfig(source, ''), /fixed approved Chromium executable/);
  assert.throws(() => buildPrivateBrowserRuntimeConfig(source, '/tmp/chrome'), /fixed approved Chromium executable/);
  assert.throws(() => buildPrivateBrowserRuntimeConfig({ browser: { browserName: 'chromium', launchOptions: { chromiumSandbox: false } } }, TRUSTED_CHROMIUM_EXECUTABLE), /chromiumSandbox=true/);
});
