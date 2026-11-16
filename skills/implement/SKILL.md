# IMPLEMENT phase skill

Read the task specification, current approved plan, existing modules and earlier review gaps. Implement only the plan, add unit/integration tests, execute relevant tests and report actual exit status and failures. Document deviations and reasons. If stuck, report blocker; never assert tests pass without running them.

## Required handoff
The runner prompt specifies `tasks/<TASK-ID>/handoffs/<phase>-cycle<N>.json`. Write UTF-8 JSON containing:
```json
{"task_id":"TASK-001","phase":"implement","cycle":1,"summary":"...","changed_files":[],"decisions":[],"tests":[{"command":"...","exit_code":0,"notes":"..."}],"risks":[],"next_steps":[],"verdict":"N/A","gaps":[]}
```
Use actual ID/cycle; `verdict` is only `PASS` or `FAIL` for REVIEW; for other phases `N/A`. JSON file must exist even on failure; record facts rather than inventing. All findings must survive fresh context. Add detailed notes to adjacent `<phase>-cycle<N>.md` when useful. Do not edit orchestration state or commit yourself; the runner commits each phase.
