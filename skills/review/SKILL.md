# REVIEW phase skill

Independently inspect the actual diff and code, task requirements, plan, tests and earlier gaps. Run tests, inspect edge cases, and provide a verdict PASS or FAIL with actionable gap IDs. PASS only if all task acceptance criteria are met; if FAIL, provide specific remediation requirements for next PLAN. External harness checks remain authoritative.

## Required handoff
The runner prompt specifies `tasks/<TASK-ID>/handoffs/<phase>-cycle<N>.json`. Write UTF-8 JSON containing:
```json
{"task_id":"TASK-001","phase":"review","cycle":1,"summary":"...","changed_files":[],"decisions":[],"tests":[{"command":"...","exit_code":0,"notes":"..."}],"risks":[],"next_steps":[],"verdict":"PASS or FAIL","gaps":[]}
```
Use actual ID/cycle; `verdict` is only `PASS` or `FAIL` for REVIEW; for other phases `N/A`. JSON file must exist even on failure; record facts rather than inventing. All findings must survive fresh context. Add detailed notes to adjacent `<phase>-cycle<N>.md` when useful. Do not edit orchestration state or commit yourself; the runner commits each phase.
