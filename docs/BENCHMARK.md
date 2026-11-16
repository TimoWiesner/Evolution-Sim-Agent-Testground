# Benchmark method

27 dependency-ordered tasks. Identical starter and specifications; the harness picks the next ready task in a fixed order. Fresh CLI processes for every phase, isolated Git repositories. Two tracks: `sequential` (one agent at a time) and `parallel` (several agents on independent tasks in private checkouts, merged after review; merge conflicts are resolved by the model and counted) and `subagents` (sequential, but the agent may delegate to its CLI's own subagents; use is recorded). `tasks/*/task.json` is immutable specification. `state.json` in the run directory is harness-owned mutable status. Plan/implement/review use files as memory. Review is agent self-review in a fresh session plus operator-owned checks. Harness may reject phase that lacks handoff or fails external checks; it never accepts 'PASS' without both.

## Metrics and limitations
Collect per-phase duration, return code, recovery attempts, review cycles, token usage and cost if CLI reports these, Git revision, automated checks, task completion ratio and unfinished dependencies. Include model name and CLI version as recorded metadata; user should record CPU/RAM/OS and starting package registry conditions. Use same time/cost policies, model settings (where possible) and task set. No weighted score hides missing measurements: report components independently.

Suggested comparative score (only if all metrics are populated): Quality 45% (acceptance coverage and external checks), autonomy 20% (completed without operator recovery), efficiency 15% (duration and reported costs relative to baselines), architecture 20% (manual rubric). `report` emits components and an **indicative** quality/autonomy summary, NOT a complete objective aggregate without manual scoring.

## Manual rubric (0–5 each)
Modularity/interfaces; readability/testability; faithful simulation design; genetic/speciation rigor; UI operability; UI visual design (from the published screenshots); documentation/security/reproducibility. Record assessor, evidence and notes in `manual-review.json` in the run directory. Different assessors should use same rubric. `report` integrates supplied manual scores, never fabricates them.

## Safety / integrity
External checks are operator-owned and not copied to workspace. Automatic checks include handoff validation and safe noninteractive smoke verification; stronger acceptance scripts should be supplied by evaluator after implementation language emerges. CLI self-tests are not proof of correct physics. Treat speed >=100 ticks/s at 2k entities as a target to measure under recorded hardware, not a portable global invariant.
