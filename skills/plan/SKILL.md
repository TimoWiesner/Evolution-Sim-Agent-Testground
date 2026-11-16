# PLAN phase skill

Inspect the current codebase, all past handoffs, task acceptance requirements, relevant architecture. Produce a concrete ordered implementation plan with file paths, interfaces, algorithm choices, risks and tests. No feature code changes; planning documents/ADRs may be edited. If this is a replan, explicitly close every REVIEW gap.

## Required handoff
The runner prompt specifies `tasks/<TASK-ID>/handoffs/<phase>-cycle<N>.json`. Write UTF-8 JSON containing:
```json
{"task_id":"TASK-001","phase":"plan","cycle":1,"summary":"...","changed_files":[],"decisions":[],"tests":[{"command":"...","exit_code":0,"notes":"..."}],"risks":[],"next_steps":[],"verdict":"N/A","gaps":[]}
```
Use actual ID/cycle; `verdict` is only `PASS` or `FAIL` for REVIEW; for other phases `N/A`. JSON file must exist even on failure; record facts rather than inventing. All findings must survive fresh context. Add detailed notes to adjacent `<phase>-cycle<N>.md` when useful. Do not edit orchestration state or commit yourself; the runner commits each phase.
