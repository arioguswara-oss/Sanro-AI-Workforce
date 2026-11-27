#!/usr/bin/env python3
"""Read-only AST interface probe. Does not import or activate Hermes services."""
import argparse
import ast
import json
import pathlib
import subprocess

p=argparse.ArgumentParser()
p.add_argument('--source',required=True,type=pathlib.Path)
a=p.parse_args()

def function(path,name):
    tree=ast.parse((a.source/path).read_text())
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name:
            return node
    raise ValueError('required native interface missing')

bound=function('gateway/session_context.py','bound_session_env')
assert bound.args.args[0].arg=='name'
identity=function('gateway/session_context.py','set_session_vars')
assert 'actor_id' in [arg.arg for arg in identity.args.args+identity.args.kwonlyargs]
approval=function('tools/approval.py','request_tool_approval')
assert [arg.arg for arg in approval.args.args]==['tool_name','reason']
assert {'rule_key','approval_callback'} <= {arg.arg for arg in approval.args.kwonlyargs}
sha=subprocess.check_output(['git','-C',str(a.source),'rev-parse','HEAD'],text=True).strip()
print(json.dumps({'source_sha':sha,'bound_session_identity':'SOURCE_CONTRACT_PASS','actor_identity':'SOURCE_CONTRACT_PASS','native_approval_signature':'SOURCE_CONTRACT_PASS','live_runtime':'NOT_TESTED','activation':'NO_GO'}))
