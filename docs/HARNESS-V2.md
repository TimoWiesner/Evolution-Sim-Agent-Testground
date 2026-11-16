# Harness v2 engineering notes

- Each task phase gets a fresh CLI subprocess. All relevant context is loaded from workspace files and the explicit absolute handoff destination.
- OpenCode v2 uses `--standalone` to avoid user-level shared daemon session association, and `--dir` plus subprocess `cwd` to identify the workspace.
- Task descriptions and skill sources are copied from the operator package. Only benchmark-controlled immutable files are integrity-checked. Generated `handoffs/` files are excluded.
- JSON handoff is a required contractual artifact; missing / malformed files receive `HANDOFF_INVALID` rather than an uncaught `FileNotFoundError`.
- A per-agent OS `flock` prevents two runs from mutating the same workspace simultaneously. The runner writes `inflight.json` before executing a phase and removes it after persistence.
- A phase commit is created after execution even when a phase fails; commit description includes the failure class. This preserves diagnostic file changes. On integrity violation the protected files are restored from operator copies before commit (incident recorded in the event).
- Recovery retries the **same phase** with new context; previous handoffs are archived. On exhaustion the task becomes `BLOCKED` and unlocked independent tasks can run.
- All CLI stdout JSONL streams to a file immediately; a small event filter shows succinct live activity. Raw logs are sensitive and should not be publicly shared unredacted.
- The generic acceptance script only checks minimum harness criteria. The benchmark is not yet a complete, independent scientific evaluation of simulation quality.
- CLI flags are version-sensitive. Verify on the installation under test with `claude --help`, `codex exec --help`, `opencode run --help` before a multi-day run.
- This package deliberately does **not** migrate existing partially failed v1 runs. Start v2 in a fresh directory; maintain old runs separately for forensics.
