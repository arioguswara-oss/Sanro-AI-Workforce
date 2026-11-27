import test from 'node:test';
import assert from 'node:assert/strict';
import { parseNamespaceSandbox } from '../scripts/chromium-sandbox-diagnostics.mjs';

test('accepts explicit active Chromium sandbox table row', () => {
  assert.deepEqual(parseNamespaceSandbox({ rows: [{ cells: ['Namespace Sandbox', 'Yes'] }] }), {
    status: 'ACTIVE', active: true, source: 'chrome://sandbox Namespace Sandbox row',
  });
});

test('rejects explicitly disabled namespace sandbox', () => {
  assert.equal(parseNamespaceSandbox({ rows: [['Namespace Sandbox', 'No']] }).status, 'INACTIVE');
});

test('fails closed when diagnostics are missing or value is unknown', () => {
  assert.equal(parseNamespaceSandbox({ bodyText: 'Sandbox status unavailable' }).status, 'UNVERIFIED');
  assert.equal(parseNamespaceSandbox({ rows: [['Namespace Sandbox', 'Enabled']] }).active, false);
});

test('accepts documented text/table formatting variants only with explicit Yes', () => {
  assert.equal(parseNamespaceSandbox({ bodyText: 'Namespace Sandbox\nYes' }).active, true);
  assert.equal(parseNamespaceSandbox({ bodyText: 'Namespace Sandbox | Yes' }).active, true);
  assert.equal(parseNamespaceSandbox({ rows: [{ label: ' namespace   sandbox ', value: ' YES ' }] }).active, true);
});

test('rejects contradictory duplicate statuses', () => {
  assert.equal(parseNamespaceSandbox({ rows: [['Namespace Sandbox', 'Yes'], ['Namespace Sandbox', 'No']] }).status, 'UNVERIFIED');
});
