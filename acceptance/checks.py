"""Independent, operator-owned baseline checks.

This is intentionally architecture-neutral: product-level tests are external and optional,
not a claim of simulation correctness.
"""
import json
import pathlib
import subprocess
import sys

w=pathlib.Path(sys.argv[1]).resolve()
task=sys.argv[2];phase=sys.argv[3]
assert phase in ('plan','implement','review') and task.startswith('TASK-')
for file in ('AGENTS.md','docs/STATE.md','docs/ARCHITECTURE.md',f'tasks/{task}/task.json',f'tasks/{task}/task.md'):
    assert (w/file).is_file(), f'missing {file}'
assert subprocess.run(['git','rev-parse','--is-inside-work-tree'],cwd=w,capture_output=True).returncode==0
assert not subprocess.run(['git','remote'],cwd=w,capture_output=True,text=True).stdout.strip(),'remote detected'
assert json.loads((w/f'tasks/{task}/task.json').read_text())
print('Operator baseline PASS (NOT a product correctness certification)')
