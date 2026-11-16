# Evolution Agent Benchmark v1

A testing ground for agentic coding. Each coding agent is given the same 27 dependent tasks and has to build an evolution simulation from an empty starter project. The harness drives cloud models (Claude Code, Codex) and local models (through opencode) in exactly the same way, so their results can be compared.

Every task runs through three phases, PLAN, IMPLEMENT and REVIEW. Each phase is a **new CLI process** with no chat history; the agent's only memory is the files it wrote. Work happens in a local Git repository with no remotes.

Agents run inside a rootless Podman container that sees only its own workspace, so unattended runs are safe on a normal machine.

> Status: the harness is under active development. Hidden acceptance tests, packaging and the parallel tracks are planned but not built yet.

## Quick start (Ubuntu)

```bash
sudo apt update && sudo apt install -y python3 git tmux podman
python3 -m unittest discover -s harness_tests -v
python3 run.py build-image                             # once: build the agent sandbox image
python3 run.py doctor                                  # CLIs, versions, image, profiles
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
| `host_ports` | Host loopback ports the container may reach, e.g. `[8080]` for a local model server |
| `cpus`, `memory` | Optional container limits, e.g. `4` and `8g` |

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
  home/             the container's home directory; holds a copy of the CLI login, never publish it
  logs/*.jsonl      full raw CLI events (may contain sensitive text)
  handoff-archive/  handoffs from retried phases
```

`--track` is `sequential` for now. `--run-id` defaults to `r1`; use another id to repeat a run.

## Commands

```bash
python3 run.py doctor
python3 run.py build-image
python3 run.py init    --profile local-qwen
python3 run.py run     --profile local-qwen [--run-id r2] [--max-phases N] [--quiet] [--dry-run] [--refresh-login]
python3 run.py report  --profile local-qwen
python3 run.py compare [--out DIR]
python3 run.py unblock --profile local-qwen --task TASK-005 --phase implement --cycle 1
```

- `compare` reads every run under the runs root and writes `comparison.md` and `comparison.json`: one summary row per profile and track (median when there are several runs, with the run count shown) and one detail row per run.
- `--quiet` hides the live event summary; the full JSONL log is still written.
- `--refresh-login` copies your current host CLI login into the run again, for when the run's copy has expired.
- `--no-container` runs the agent directly on the host instead of in the sandbox; `--allow-unsafe` then lets the CLI skip its permission prompts. Read [docs/SECURITY.md](docs/SECURITY.md) first. A run stays in the mode it started in.
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
- `container/Containerfile`: the agent sandbox image (Ubuntu 24.04, Python, Rust, Node, build tools).
- `docs/`: [method](docs/BENCHMARK.md), [engineering notes](docs/HARNESS.md), [security](docs/SECURITY.md).

## What is and is not measured today

Reports and the comparison give, per run:

- tasks done and blocked, and the share of done tasks that passed review in the first cycle
- phases attempted and failed, by failure class (`HANDOFF_INVALID`, `CLI_FAILURE`, `TIMEOUT`, `ACCEPTANCE_FAILURE`, `INFRA_INTEGRITY`)
- operator interventions (`unblock`)
- agent wall time
- tokens split into fresh input, cached input and output, and cost, where the CLI reports them

Token counts are normalised across CLIs: cached input is listed separately because it dominates Claude Code's totals and is billed at a fraction of the price. Missing usage is shown as unknown, never as zero. Codex reports no cost. Speed and cost are separate columns and are never folded into a quality figure.

A task currently counts as done when the agent's own review says PASS and the baseline checks hold. Those checks confirm only that the workspace is intact, **not** that the simulation works. Until the hidden acceptance tests exist, judge product quality with the manual rubric in `acceptance/MANUAL_REVIEW.md`.

## Safety

Each run has its own container. The agent is root inside it and may install anything, but it can only see its workspace, a private home directory and the read-only CLI binary. It has outbound internet access and cannot reach services on the host, apart from ports a profile lists in `host_ports`. The host's own CLI binaries are mounted in, so the container runs exactly the CLI version recorded in `run.json`.

The agent does get a copy of the CLI login, and a container is not a VM. [docs/SECURITY.md](docs/SECURITY.md) lists what is and is not protected.

Task specifications, skills and root agent instructions are checked against the originals after every phase and restored if changed.
