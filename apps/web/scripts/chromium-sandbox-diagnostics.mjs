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

// Chromium's chrome://sandbox reports a table row named "Namespace Sandbox"
// with an explicit Yes/No value. Unknown or missing values never count as PASS.
export function parseNamespaceSandbox(diagnostics) {
  const candidates = [];
  for (const row of Array.isArray(diagnostics?.rows) ? diagnostics.rows : []) {
    const cells = Array.isArray(row) ? row : Array.isArray(row?.cells) ? row.cells : [row?.label, row?.value];
    if (normalize(cells[0]) === 'namespace sandbox') candidates.push(normalize(cells[1]));
  }
  candidates.push(...rowsFromText(diagnostics?.bodyText).filter((row) => normalize(row.label) === 'namespace sandbox').map((row) => normalize(row.value)));
  const distinct = [...new Set(candidates)];
  if (distinct.length !== 1) return { status: 'UNVERIFIED', active: false, reason: distinct.length ? 'conflicting namespace sandbox values' : 'namespace sandbox status missing' };
  if (distinct[0] === 'yes') return { status: 'ACTIVE', active: true, source: 'chrome://sandbox Namespace Sandbox row' };
  if (distinct[0] === 'no') return { status: 'INACTIVE', active: false, reason: 'Chromium reports Namespace Sandbox: No' };
  return { status: 'UNVERIFIED', active: false, reason: `unrecognized namespace sandbox value: ${distinct[0]}` };
}
