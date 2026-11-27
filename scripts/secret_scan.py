"""Scan tracked public files for credential-shaped literals; never print matches."""
import pathlib
import re
import subprocess
import sys

PATTERNS = [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
            r'\bgh[pousr]_[A-Za-z0-9]{30,}\b', r'\bgithub_pat_[A-Za-z0-9_]{40,}\b',
            r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b', r'\bAKIA[A-Z0-9]{16}\b',
            r'\b[0-9]{8,12}:[A-Za-z0-9_-]{35}\b']
paths = subprocess.check_output(['git', 'ls-files', '-z']).decode().split('\0')
findings = []
for name in filter(None, paths):
    path = pathlib.Path(name)
    if not path.is_file():
        continue
    data = path.read_text(errors='replace')
    if any(re.search(pattern, data) for pattern in PATTERNS):
        findings.append(name)
print(f'secret_scan files={len(list(filter(None, paths)))} findings={len(findings)}')
for name in findings:
    print(f'credential-shaped literal in {name}')
sys.exit(bool(findings))
