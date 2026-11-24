#!/usr/bin/env python3
"""One isolated acceptance entry point. Never starts live Hermes or changes cron.

Worker cases are explicitly NOT TESTED when kernel confinement is unavailable.
Use --require-worker on the authorized host to make that condition a hard failure.
"""
import argparse
import contextlib
import hashlib
import io
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from landlock_sandbox import landlock_abi

UNSUPPORTED = {
    'test_hermes_adapter.AdapterTests.test_45_second_job_nonblocking_and_foreground_response',
    'test_hermes_adapter.AdapterTests.test_completion_result_and_secret_redaction',
    'test_hermes_adapter.AdapterTests.test_landlock_denies_host_and_other_project_paths_but_allows_project_work',
    'test_hermes_adapter.AdapterTests.test_supervisor_shutdown_interrupts_active_job',
    'test_hermes_native_plugin.NativePluginTests.test_verified_register_tool_contract_and_scoped_job',
    *('test_worker.WorkerTests.' + name for name in (
        'test_child_network_and_process_group_escape_are_denied',
        'test_conversation_responsive_while_job_runs', 'test_fast_process_exit_preserves_return_code',
        'test_fifo_completion_and_logs', 'test_running_cancellation', 'test_timeout')),
}

class CapabilityBlocked(unittest.TestCase):
    def __init__(self, original):
        super().__init__()
        self.original = original
    def id(self):
        return self.original.id()
    def runTest(self):
        self.skipTest('NOT TESTED: Landlock unavailable; real execution remains fail-closed')

def flatten(suite):
    for case in suite:
        if isinstance(case, unittest.TestSuite):
            yield from flatten(case)
        else:
            yield case

def command(args, cwd, report):
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    print(result.stdout)
    report['commands'].append({'command':args,'status':'PASS' if result.returncode == 0 else 'FAIL','output_sha256':hashlib.sha256(result.stdout.encode()).hexdigest()})
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-worker', action='store_true')
    parser.add_argument('--source-ref', default='HEAD')
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    abi = landlock_abi()
    source_sha = subprocess.check_output(['git','rev-parse',args.source_ref], cwd=ROOT, text=True).strip()
    source_tree = subprocess.check_output(['git','rev-parse',args.source_ref+'^{tree}'], cwd=ROOT, text=True).strip()
    current_tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    if source_tree != current_tree or subprocess.run(['git','diff','--quiet','HEAD'],cwd=ROOT).returncode:
        raise SystemExit('source ref differs from current clean tracked source')
    report = {'schema_version':1,'source_sha':source_sha,'source_tree':source_tree,'landlock_abi':abi,'scope':'ISOLATED_SYNTHETIC_CANDIDATE','live_runtime':'NOT_TESTED','commands':[]}
    loader=unittest.TestLoader()
    root_suite=loader.discover(str(ROOT), pattern='test_*.py')
    # Separate JD-03 directories are not Python packages, so discover explicitly.
    cases=list(flatten(root_suite))
    for directory in ('structured-inspection','approval-gate'):
        separate=unittest.TestLoader().discover(str(ROOT/'integrations/hermes'/directory),pattern='test_*.py',top_level_dir=str(ROOT/'integrations/hermes'/directory))
        cases.extend(flatten(separate))
    suite=unittest.TestSuite(CapabilityBlocked(case) if not abi and case.id() in UNSUPPORTED else case for case in cases)
    output=io.StringIO()
    with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
        result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    print(output.getvalue())
    report['python']={'run':result.testsRun,'pass':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),'fail':len(result.failures),'error':len(result.errors),'not_tested':len(result.skipped),'skipped':[{'test':case.id(),'reason':reason} for case,reason in result.skipped],'failed_tests':[case.id() for case,_ in result.failures+result.errors]}
    passed=result.wasSuccessful()
    node=['node','--test']
    if not abi:
        node.append('--test-name-pattern=^(?!approved fixed-profile jobs)')
    passed=command(node,ROOT/'apps/api',report) and passed
    web=ROOT/'apps/web'
    if not (web/'node_modules/vite').exists():
        passed=command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],web,report) and passed
    for cmd in (['npm','run','build'],['node','node_modules/vite/bin/vite.js','build','--config','vite.monitor.config.js'],['node','--test','test/monitor-render.test.js']):
        passed=command(cmd,web,report) and passed
    passed=command([sys.executable,'scripts/secret_scan.py'],ROOT,report) and passed
    passed=command(['git','diff','--check'],ROOT,report) and passed
    report['portable_result']='PASS' if passed else 'FAIL'
    report['worker_runtime']='REQUIRES_HOST_ACCEPTANCE' if abi else 'BLOCKED_LANDLOCK_UNAVAILABLE'
    report['activation']='NO_GO'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if passed and (abi or not args.require_worker) else 1

if __name__=='__main__':
    raise SystemExit(main())
