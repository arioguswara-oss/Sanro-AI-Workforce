const normalize = (value) => String(value ?? '').replace(/\s+/g, ' ').trim().toLowerCase();

function rowsFromText(text) {
  const lines = String(text ?? '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const rows = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].replace(/^\|+|\|+$/g, '').trim();
    const pair = line.split(/\s{2,}|\s*\|\s*|\t/).map((part) => part.trim()).filter(Boolean);
    if (pair.length >= 2) rows.push({ label: pair[0], value: pair[1] });
    else if (/^namespace sandbox$/i.test(line) && index + 1 < lines.length) rows.push({ label: line, value: lines[index + 1] });
  }
  return rows;
}

function collectRows(diagnostics) {
  const rows = [];
  for (const row of Array.isArray(diagnostics?.rows) ? diagnostics.rows : []) {
    const cells = Array.isArray(row) ? row : Array.isArray(row?.cells) ? row.cells : [row?.label, row?.value];
    if (cells.length >= 2) rows.push({ label: normalize(cells[0]), value: normalize(cells[1]) });
  }
  rows.push(...rowsFromText(diagnostics?.bodyText).map(({ label, value }) => ({ label: normalize(label), value: normalize(value) })));
  return rows;
}

// Chromium 159 reports "Layer 1 Sandbox: Namespace" rather than a row named
// "Namespace Sandbox". Every required defense needs its explicit expected value.
export function parseChromiumSandbox(diagnostics) {
  const rows = collectRows(diagnostics);
  const required = [
    ['Layer 1 Sandbox', 'namespace'],
    ['PID namespaces', 'yes'],
    ['Network namespaces', 'yes'],
    ['Seccomp-BPF sandbox', 'yes'],
    ['Seccomp-BPF sandbox supports TSYNC', 'yes'],
  ];
  const checks = {};
  const failures = [];
  for (const [label, expected] of required) {
    const values = [...new Set(rows.filter((row) => row.label === normalize(label)).map((row) => row.value))];
    const key = label;
    if (values.length === 1 && values[0] === expected) checks[key] = { status: 'PASS', value: values[0] };
    else {
      checks[key] = { status: 'FAIL', values };
      failures.push(values.length > 1 ? `${label}: conflicting values` : values.length === 0 ? `${label}: missing` : `${label}: expected ${expected}, got ${values[0]}`);
    }
  }
  const nonBrokerValues = [...new Set(rows.filter((row) => row.label === normalize('Ptrace Protection with Yama LSM (Non-broker)')).map((row) => row.value))];
  const warnings = [];
  if (nonBrokerValues.includes('no')) warnings.push('Yama Non-broker protection reports No');
  else if (nonBrokerValues.length !== 1 || nonBrokerValues[0] !== 'yes') warnings.push('Yama Non-broker protection is missing or unrecognized');
  checks['Yama Non-broker'] = { status: warnings.length ? 'WARNING' : 'PASS', values: nonBrokerValues };
  const brokerValues = [...new Set(rows.filter((row) => row.label === normalize('Ptrace Protection with Yama LSM (Broker)')).map((row) => row.value))];
  checks['Yama Broker'] = { status: brokerValues.length === 1 && brokerValues[0] === 'yes' ? 'PASS' : 'WARNING', values: brokerValues };
  if (checks['Yama Broker'].status === 'WARNING') warnings.push('Yama Broker protection is missing or unrecognized');

  return {
    status: failures.length ? 'FAIL' : 'PASS',
    active: failures.length === 0,
    source: 'chrome://sandbox diagnostics',
    checks,
    warnings,
    failures,
  };
}
