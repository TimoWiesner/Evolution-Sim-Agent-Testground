# Benchmark method

28 dependency-ordered tasks. Identical starter and specifications; the harness picks the next ready task in a fixed order. Fresh CLI processes for every phase, isolated Git repositories. Two tracks: `sequential` (one agent at a time) and `parallel` (several agents on independent tasks in private checkouts, merged after review; merge conflicts are resolved by the model and counted) and `subagents` (sequential, but the agent may delegate to its CLI's own subagents; use is recorded). `tasks/*/task.json` is immutable specification. `state.json` in the run directory is harness-owned mutable status. Plan/implement/review use files as memory. Review is agent self-review in a fresh session plus operator-owned checks. Harness may reject phase that lacks handoff or fails external checks; it never accepts 'PASS' without both.

## Metrics and limitations
Collect per-phase duration, return code, recovery attempts, review cycles, token usage and cost if CLI reports these, Git revision, automated checks, task completion ratio and unfinished dependencies. Include model name and CLI version as recorded metadata; user should record CPU/RAM/OS and starting package registry conditions. Use same time/cost policies, model settings (where possible) and task set. No weighted score hides missing measurements: report components independently.

Suggested comparative score (only if all metrics are populated): Quality 45% (acceptance coverage and external checks), autonomy 20% (completed without operator recovery), efficiency 15% (duration and reported costs relative to baselines), architecture 20% (manual rubric). `report` emits components and an **indicative** quality/autonomy summary, NOT a complete objective aggregate without manual scoring.

## Manual rubric (0–5 each)
Modularity/interfaces; readability/testability; faithful simulation design; genetic/speciation rigor; UI operability; UI visual design (from the published screenshots); documentation/security/reproducibility. Record assessor, evidence and notes in `manual-review.json` in the run directory. Different assessors should use same rubric. `report` integrates supplied manual scores, never fabricates them.

## Safety / integrity
External checks are operator-owned and not copied to workspace. Automatic checks include handoff validation and safe noninteractive smoke verification; stronger acceptance scripts should be supplied by evaluator after implementation language emerges. CLI self-tests are not proof of correct physics. Treat speed >=100 ticks/s at 2k entities as a target to measure under recorded hardware, not a portable global invariant.

## Versions

Runs are only directly comparable within one benchmark version. The version is stored in each run's `run.json`; `compare` groups and labels runs by it.

- **Version 1** (until 2026-11-21): all runs up to and including `gpt-astra/sequential/r1`.
- **Version 2** (2026-11-21): two wording clarifications, nothing else changed (other tasks, skills, prompt and hidden suite are the same).
  - TASK-002: "`./evosim version` prints the contract JSON after `./setup.sh` in a fresh container" now reads "... in a clean checkout of the repository (for example `git clone` into an empty directory). The harness checks the same in a fresh container that it provides; the agent does not start containers itself."
  - `docs/CONTRACT.md`, `./setup.sh`: adds "The harness provides that container when it evaluates; agents cannot start containers inside the sandbox and check this with a clean checkout instead."
  - Reason: in `gpt-astra/sequential/r1` the model read "fresh container" literally, tried to start a container inside the sandbox (not possible there) and failed TASK-002 review in four cycles, so 26 tasks never started. Every other profile had passed the same criterion in the first cycle.
