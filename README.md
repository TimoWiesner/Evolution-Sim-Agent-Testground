# Evolution Agent Benchmark v2

**27 original task specifications, unchanged.** The new harness uses isolated local Git repositories and independent agent processes for PLAN, IMPLEMENT and REVIEW. Neither GitHub nor Git remotes are required.

## Ubuntu quick start

```bash
sudo apt update && sudo apt install -y python3 git tmux
python3 -m unittest discover -s harness_tests -v
python3 run.py doctor
python3 run.py init --agent opencode
python3 run.py run --agent opencode --dry-run
python3 run.py run --agent opencode --max-phases 1
# after smoke test:
tmux new -s evolution
python3 run.py run --agent opencode
```

Run with `--agent claude` or `--agent codex` for other providers, after CLI installation and authentication. `--model <id>` chooses a model. Every phase starts a **new CLI process** and does not resume previous chat sessions. `--quiet` hides concise live events but still records full JSONL. `--allow-unsafe` enables the CLIs' permissive modes; only do this inside a dedicated disposable VM, never with personal credentials mounted.

To stop with Ctrl+C: if possible stop between phases. An interrupted subprocess may leave `runs/<agent>/inflight.json`, which is detected at the next startup. Prior recorded phase state is preserved; rerun may repeat interrupted work. Agent edits are not deleted. Recoveries use new processes and retain earlier logs and handoffs in the archive.

## Commands

```bash
python3 run.py doctor
python3 run.py init --agent opencode
python3 run.py run --agent opencode --max-phases 1
python3 run.py run --agent opencode
python3 run.py run --agent opencode --quiet
python3 run.py report --agent opencode
python3 run.py unblock --agent opencode --task TASK-005 --phase implement --cycle 1
```

`unblock` is an **operator intervention**: it keeps implementation files and Git history, resets recovery to zero, and changes only the chosen task. Such interventions must be disclosed in comparisons. The default max cycles is 3, technical retry count is 1; unrelated unlocked tasks can continue when one task blocks.

## Layout

- `tasks/TASK-*/task.md` and `task.json`: **immutable original requirements**.
- `skills/{plan,implement,review}/SKILL.md`: distributed into each workspace.
- `starter/`: initial project files, AGENTS.md and CLAUDE.md.
- `harness/core.py`: runner and CLI event stream adapters.
- `harness_tests/`: fake-agent end-to-end tests and unit tests.
- `acceptance/`: operator-owned baseline checks, run from outside workspace.
- `runs/<agent>/workspace`: independent local Git repo with no remotes.
- `runs/<agent>/logs/*.jsonl`: full raw CLI events (may contain sensitive text).
- `runs/<agent>/state.json`: authoritative runner state.
- `runs/<agent>/report.json`: report with progress and failure-class breakdown.
- `runs/<agent>/handoff-archive`: preserved previous handoffs from retries.

### Live output

Concisely displays phase starts, tool names, command starts, completed steps, failures and results **as surfaced by the CLI**. It does not claim to extract private model reasoning or print unrestricted thinking streams. Claude uses `--output-format stream-json --verbose`; Codex uses `exec --json`; OpenCode v2 uses `run --standalone --format json --dir <workspace>`. Availability and exact event shapes vary by CLI release. Always verify `run.py doctor`, the first smoke test, and locally installed `--help` output. Raw JSONL is always saved as phase progresses.

### Independence and safety

Only task specifications, skill files and root agent instructions are protected. Task-local `handoffs/*.json` and `*.md`, docs and implementation files are **writable**. The runner verifies controlled files against operator originals and runs its own baseline checks after each phase. It classifies `HANDOFF_INVALID`, `CLI_FAILURE`, `TIMEOUT`, `ACCEPTANCE_FAILURE`, and `INFRA_INTEGRITY` separately. Validation is not proof of simulation behavior: the existing external checker currently asserts framework-level invariants, **not the full 27 feature requirements**. Product validation still needs independent black-box tests and manual UI/architecture assessment.

The runner does not configure remotes or push. CLI agents run with filesystem access; this is **not a hard OS sandbox**. Run in an isolated VM, and keep package installation privilege limited. Sharing the benchmark template on GitHub is optional; `runs/` remains ignored.

### Fair benchmark comparison

Use the same starting ZIP, hardware class, provider-specific permissions, available models/budgets and evaluator version; note that model quality and CLI differ. Compare completion ratio, test outcomes, manual review, attempts, wall time and available usage/cost; missing provider usage is shown as unknown, never silently assumed zero. Never count harness-side failures as agent reasoning failures. Test product capabilities separately after the run.
