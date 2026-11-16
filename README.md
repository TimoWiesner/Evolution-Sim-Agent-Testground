# Evolution Agent Benchmark v1

A testing ground for agentic coding. Each coding agent is given the same 27 dependent tasks and has to build an evolution simulation from an empty starter project. The harness drives cloud models (Claude Code, Codex) and local models (through opencode) in exactly the same way, so their results can be compared.

Every task runs through three phases, PLAN, IMPLEMENT and REVIEW. Each phase is a **new CLI process** with no chat history; the agent's only memory is the files it wrote. Work happens in a local Git repository with no remotes.

> Status: the harness is under active development. Hidden acceptance tests, container isolation, cross-run comparison, packaging and the parallel tracks are planned but not built yet.

## Quick start (Ubuntu)

```bash
sudo apt update && sudo apt install -y python3 git tmux
python3 -m unittest discover -s harness_tests -v
python3 run.py doctor                                  # CLIs, versions, profiles
python3 run.py run --profile claude-sonnet --dry-run   # show the command, call nothing
python3 run.py run --profile claude-sonnet --max-phases 1
# after the smoke test:
tmux new -s evolution
python3 run.py run --profile claude-sonnet
```

## Profiles: choosing CLI and model

A profile is a named combination of CLI, model and settings in `benchmark.json`. Values not set in a profile come from `defaults`.

```json
"profiles": {
  "claude-opus":   { "cli": "claude", "model": "opus" },
  "claude-sonnet": { "cli": "claude", "model": "sonnet" },
  "gpt-luna":      { "cli": "codex", "model": "gpt-6-luna" },
  "local-qwen":    { "cli": "opencode", "model": "llama.cpp/qwen3.6-35b-a3b", "phase_timeout_seconds": 7200 }
}
```

| Field | Meaning |
|---|---|
| `cli` | `claude`, `codex` or `opencode` |
| `model` | Model id passed to the CLI; `null` uses the CLI's default |
| `phase_timeout_seconds` | Time limit per phase; raise it for slow local hardware |
| `max_turns` | Claude only; `null` leaves the CLI's own limit |
| `extra_args` | Extra CLI arguments |
| `env` | Extra environment variables for the CLI process |

Local models are any OpenAI-compatible endpoint (llama.cpp, Ollama, LM Studio) registered as a provider in your opencode configuration; the profile names it as `provider/model`.

A run is locked to the profile settings it started with. If you change a profile, start a new run with `--run-id`; the harness refuses to continue the old one, so no run can mix models.

## Runs

Run data is stored **outside this repository**, by default under `~/evo-runs` (`runs_root` in `benchmark.json`):

```
~/evo-runs/<profile>/<track>/<run-id>/
  run.json          model, settings, CLI version, harness commit, host hardware
  state.json        authoritative runner state
  report.json       progress, failure classes, tokens, cost, time
  workspace/        the agent's local Git repository (no remotes)
  logs/*.jsonl      full raw CLI events (may contain sensitive text)
  handoff-archive/  handoffs from retried phases
```

`--track` is `sequential` for now. `--run-id` defaults to `r1`; use another id to repeat a run.

## Commands

```bash
python3 run.py doctor
python3 run.py init    --profile local-qwen
python3 run.py run     --profile local-qwen [--run-id r2] [--max-phases N] [--quiet] [--dry-run] [--allow-unsafe]
python3 run.py report  --profile local-qwen
python3 run.py unblock --profile local-qwen --task TASK-005 --phase implement --cycle 1
```

- `--quiet` hides the live event summary; the full JSONL log is still written.
- `--allow-unsafe` switches the CLI to its permissive mode with full file and network access. See [docs/SECURITY.md](docs/SECURITY.md) before using it.
- `unblock` is an **operator intervention** and must be disclosed when comparing results. It keeps the code and Git history and resets the retry counter for one task.
- Ctrl+C: stop between phases if possible. An interrupted phase leaves `inflight.json`, which is reported on the next start; the phase is then repeated.

Tasks are worked in a fixed order (started tasks first, then the lowest ready task ID), so every profile sees the same sequence. A failed phase is retried once; after that the task is `BLOCKED` and independent tasks continue. A failed review sends the task back to PLAN, up to three cycles.

## Layout

- `tasks/TASK-*/task.md` and `task.json`: task specifications.
- `skills/{plan,implement,review}/SKILL.md`: phase instructions copied into each workspace.
- `starter/`: initial project files, `AGENTS.md` and `CLAUDE.md`.
- `harness/core.py`: runner and CLI adapters.
- `harness_tests/`: unit tests and an end-to-end test with a fake agent.
- `acceptance/`: operator-owned baseline checks.
- `docs/`: [method](docs/BENCHMARK.md), [engineering notes](docs/HARNESS.md), [security](docs/SECURITY.md).

## What is and is not measured today

The report gives completion ratio, phases attempted, failure classes (`HANDOFF_INVALID`, `CLI_FAILURE`, `TIMEOUT`, `ACCEPTANCE_FAILURE`, `INFRA_INTEGRITY`), wall time, and tokens and cost where the CLI reports them. Missing usage is shown as unknown, never as zero.

A task currently counts as done when the agent's own review says PASS and the baseline checks hold. Those checks confirm only that the workspace is intact, **not** that the simulation works. Until the hidden acceptance tests exist, judge product quality with the manual rubric in `acceptance/MANUAL_REVIEW.md`.

## Safety

Agents run with ordinary filesystem access; a workspace is not a sandbox. Task specifications, skills and root agent instructions are checked against the originals after every phase and restored if changed. Run unattended benchmarks only in a disposable VM or container without valuable credentials.
