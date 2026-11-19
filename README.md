# Evolution Agent Benchmark v1

A testing ground for agentic coding. Each coding agent is given the same 28 dependent tasks and has to build an evolution simulation from an empty starter project. The harness drives cloud models (Claude Code, Codex) and local models (through opencode) in exactly the same way, so their results can be compared.

Every task runs through three phases, PLAN, IMPLEMENT and REVIEW. Each phase is a **new CLI process** with no chat history; the agent's only memory is the files it wrote. Work happens in a local Git repository with no remotes.

Agents run inside a rootless Podman container that sees only its own workspace, so unattended runs are safe on a normal machine.

> Status: the harness and all three tracks (sequential, parallel, subagents) are built. Full benchmark runs are still to come.

Published results: [Evolution-Sim-Agent-Results](https://github.com/TimoWiesner/Evolution-Sim-Agent-Results).

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
| `phase_timeout_seconds` | Time limit per phase; raise it for slow local hardware. Tasks with `timeout_factor` in `task.json` get a multiple of it |
| `max_turns` | Claude only; `null` leaves the CLI's own limit |
| `extra_args` | Extra CLI arguments |
| `env` | Extra environment variables for the CLI process |
| `host_ports` | Host loopback ports the container may reach, e.g. `[8080]` for a local model server |
| `cpus`, `memory` | Optional container limits, e.g. `4` and `8g` |
| `workers` | Parallel track: agents working at the same time (default 3; 1 for the local profile) |

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
  workers/TASK-*/   parallel track only: private checkout of each task in progress
  home/             the container's home directory; holds a copy of the CLI login, never publish it
  logs/*.jsonl      full raw CLI events (may contain sensitive text)
  handoff-archive/  handoffs from retried phases
  eval/             hidden test results and logs per completed task
```

`--track` is `sequential` (default), `parallel` or `subagents`. `--run-id` defaults to `r1`; use another id to repeat a run.

## Commands

```bash
python3 run.py doctor
python3 run.py build-image
python3 run.py init    --profile local-qwen
python3 run.py run     --profile local-qwen [--run-id r2] [--max-phases N] [--quiet] [--dry-run] [--refresh-login] [--no-eval]
python3 run.py report  --profile local-qwen
python3 run.py evaluate --profile local-qwen           # score the current state again
python3 run.py compare [--out DIR]
python3 run.py package --profile local-qwen           # build and write the run into the results repository
python3 run.py publish [--dry-run]                    # push the results repository, upload executables
python3 run.py unblock --profile local-qwen --task TASK-005 --phase implement --cycle 1
```

- `compare` reads every run under the runs root and writes `comparison.md` and `comparison.json`: one summary row per profile and track (median when there are several runs, with the run count shown) and one detail row per run.
- `--quiet` hides the live event summary; the full JSONL log is still written.
- `--refresh-login` copies your current host CLI login into the run again, for when the run's copy has expired.
- `--no-container` runs the agent directly on the host instead of in the sandbox; `--allow-unsafe` then lets the CLI skip its permission prompts. Read [docs/SECURITY.md](docs/SECURITY.md) first. A run stays in the mode it started in.
- `unblock` is an **operator intervention** and must be disclosed when comparing results. It keeps the code and Git history and resets the retry counter for one task.
- Provider limits: when a CLI reports a usage or rate limit, the refused call is not counted as a failure. The run waits until the limit resets (up to 6 hours, `max_limit_wait_seconds`) and repeats the phase; `--stop-on-limit` ends the run instead so you can resume it later.
- Outages: a call that fails because the connection, the provider, the login or a local model server is down is not counted as a failure either. The phase is repeated after 1, 5, 15 and 30 minutes (`infra_retry_waits_seconds`); if it still fails, the run stops with a message and continues when you start the same command again. A rejected login is first replaced by a fresh copy of the host login. For profiles with `host_ports` the harness checks before and during every call that the local server answers. After six refused calls in a row without a completed phase (`max_refusals_in_a_row`) the run also stops.
- `--workers N` sets the number of agents for a new parallel run; it cannot change later.
- Stopping: Ctrl+C, a closed terminal and a shutdown all end the running agent and stop the container. An interrupted phase leaves `inflight.json`, which is reported on the next start; the phase is then repeated. `run` also stops the run's container when it starts, so nothing from a killed run keeps working.
- Long runs: start them where a closed window or a sleeping machine cannot end them, for example `tmux new -s bench` and then `systemd-inhibit --what=sleep:idle python3 run.py run --profile …`.
- Resuming: every start of `run` continues where the run stopped. It reports phases that were interrupted (`interruptions` in `state.json`), scores finished tasks that have no hidden-test result yet, and notes a changed CLI version in `run.json`. A repeated call writes a new log file (`….try2.jsonl`). `state.json` is written with a backup copy (`state.json.bak`) that is used when the file is damaged. The run stops with a message when less than `min_free_disk_gb` (10) is free.
- Clean phases: in the sequential and subagent tracks the container is restarted before every phase, so no process of an earlier phase is still running; files and installed packages stay. The container is limited to 16 GB of memory (`container.memory`).
- Repairs: before each phase the harness removes stale Git lock files and Git remotes and restores changed benchmark files in the workspace; this is stored as `repairs` in the phase's event.

Tasks are worked in a fixed order (started tasks first, then the lowest ready task ID), so every profile sees the same sequence. A failed phase is retried once; after that the task is `BLOCKED` and independent tasks continue. A failed review sends the task back to PLAN, up to three cycles.

## Tracks

| Track | How the 28 tasks are worked |
|---|---|
| `sequential` | One agent at a time, one task after the other. |
| `parallel` | Up to N agents at the same time, each on a different task whose prerequisites are done. The harness does the splitting. |
| `subagents` | One task after the other, as in `sequential`, but the agent may hand work to its CLI's own subagents. The model does the splitting. |

```bash
python3 run.py run --profile claude-sonnet --track parallel [--workers 3]
```

In the parallel track every task is developed in its own checkout, a local clone of the main line taken when the task starts. The task goes through the same PLAN, IMPLEMENT and REVIEW phases there. When its review passes, the harness merges it into the main workspace:

- If Git can merge it alone, no agent is involved.
- On a conflict, **one extra agent call** (a MERGE phase) has to resolve it in the main workspace. It is retried once like any phase; if conflict markers remain or the merge was abandoned, the main line is put back and the task is `BLOCKED`.
- A task only counts as done, and unlocks the tasks that depend on it, once it is merged.

The number of workers is fixed for a run and recorded in `run.json`. `compare` adds a parallel section: elapsed time, how many agents were busy on average, speed-up against the sequential run of the same profile, and the number of merges, conflicts and failed merges. Hidden evaluations run beside the workers and are not part of the elapsed time.

Things to know when reading parallel results:

- The task graph limits what can run side by side: at most two to four tasks are ready at the same time, and the first two tasks are strictly serial.
- Checkouts do not share build output or installed project dependencies, so each task may repeat `./setup.sh`. All workers share one container, including its system packages.
- Speed figures measured by the hidden suite during a run can be disturbed by agents working at the same time. Run `evaluate` once the run has finished for a clean final measurement.
- With subscription logins, several agents share one rate limit.

### Subagent track

```bash
python3 run.py run --profile claude-sonnet --track subagents
```

Everything is as in the sequential track except one paragraph in the phase prompt: delegation to subagents is allowed and encouraged where it helps, not required. Whether and how to delegate is the model's decision, and that decision is what the track measures. `compare` shows how many agent calls delegated work, how many subagents were started, and agent time against the sequential run of the same profile.

What each CLI reports:

| CLI | Delegation happened | Number of subagents | Subagent tokens and cost |
|---|---|---|---|
| Claude Code | yes | yes | included |
| Codex | yes | not reported, shown as "—" | not verified |
| opencode | yes (read from `task` tool calls, not yet tested live) | yes | not verified |

Codex runs without `--ephemeral` in this track, because its subagents need a stored session.

## Layout

- `tasks/TASK-*/task.md` and `task.json`: task specifications.
- `skills/{plan,implement,review}/SKILL.md`: phase instructions copied into each workspace.
- `starter/`: initial project files, `AGENTS.md`, `CLAUDE.md` and the interface contract `docs/CONTRACT.md`.
- `harness/core.py`: runner, CLI adapters, container isolation, evaluation and comparison.
- `harness/publish.py`: packaging and publishing of finished runs.
- `harness_tests/`: unit tests and an end-to-end test with a fake agent.
- `acceptance/`: operator-owned baseline checks.
- `container/Containerfile`: the agent sandbox image (Ubuntu 24.04, Python, Rust, Node, build tools, headless Chromium and a virtual display).
- `docs/`: [method](docs/BENCHMARK.md), [engineering notes](docs/HARNESS.md), [security](docs/SECURITY.md).

## Interface contract

Agents choose language, architecture and UI themselves, but every product must expose the same outside, defined in [`starter/docs/CONTRACT.md`](starter/docs/CONTRACT.md):

- `./setup.sh` installs everything in a fresh container, `./evosim` runs the product, `./build.sh` produces a self-contained `dist/evosim`.
- `evosim run` takes a fixed set of flags and a few fixed configuration keys and writes a fixed result JSON (populations, species, births and deaths, a state hash, speed).
- Runs must be deterministic per seed, a checkpoint resume must reproduce an uninterrupted run exactly, and extinct kinds must stay extinct.
- `evosim ui --smoke-test` must start the real UI and exit cleanly.
- `evosim ui --screenshots DIR` must write images of the real UI, which the results repository shows side by side.
- `scenarios/demo.json` is the product's demo scenario; the README's demo command uses it.

This makes products from different models testable with one black-box suite and packageable with one build step. Seven of the 28 tasks carry the matching acceptance criteria.

## Tasks

All 28 task files have the same sections, so that weaker models are not left guessing and stronger ones know where their freedom lies:

| Section | Meaning |
|---|---|
| Goal | One sentence on what the task is for. |
| Must have | Separate, checkable points. The agent's review may pass the task only if all are met. |
| Your decisions | What the agent decides and has to document. |
| Not part of this task | What belongs to other tasks. |

The three UI tasks (23 to 25) add two sections. "Must have" is a functional baseline that a small model can reach: world view, controls, inspector, parameter editing, charts. "Design freedom" hands the look and feel to the agent, with ideas but no requirements, and can never fail a task. "Screenshots" asks the product to render its own interface to PNG files; this is scored by one hidden check and published, but does not block the task.

TASK-027 (ecosystem balance) is the one task about tuning: with the batch tool in hand, the agent measures how long the food chain lasts, analyses why the first kind dies out, tries mechanism changes and records every trial. It passes on method and honesty, not on the outcome; the outcome is measured by the hidden balance figure. It runs right before TASK-028, the delivery.

The five mechanism tasks for plants and animals (11, 12, 14, 15, 16) add an "Ecology ideas" section: mechanisms that keep a food chain going without forced anti-extinction, such as regenerating resources, satiation or refuges for prey. Like design freedom, they are suggestions and can never fail a task.

The technology is open as well: any language or framework that runs in the sandbox image.

## What is and is not measured today

Reports and the comparison give, per run:

- tasks done and blocked, and the share of done tasks that passed review in the first cycle
- phases attempted and failed, by failure class (`HANDOFF_INVALID`, `CLI_FAILURE`, `TIMEOUT`, `ACCEPTANCE_FAILURE`, `INFRA_INTEGRITY`)
- operator interventions (`unblock`)
- agent wall time
- tokens split into fresh input, cached input and output, and cost, where the CLI reports them

- balance: how long plants, herbivores and carnivores coexist over 10,000 ticks, scored 0 to 100, once in the contract's example configuration with the product's default parameters and once in its own demo scenario (time limit per 10,000-tick run: 300 s and 900 s, stated in the contract; runs over the limit are listed separately instead of counting as collapse). The tasks allow collapse, so this is a figure for comparison, not a pass/fail check.

Token counts are normalised across CLIs: cached input is listed separately because it dominates Claude Code's totals and is billed at a fraction of the price. Missing usage is shown as unknown, never as zero; a sum that lacks some phases is shown as a lower bound (`≥`). Codex reports no cost. Speed and cost are separate columns and are never folded into a quality figure.

### Hidden tests

Product quality is scored by a black-box suite kept in a separate private repository, so agents cannot read it and it cannot leak into training data. It currently has 42 pass/fail checks in eight categories: contract conformance, determinism, checkpoints, ecology, robustness, performance, distributable and UI (start-up and screenshots).

- The suite runs after every completed task, on the committed state, and only uses the interface contract. A check counts once the task that owns it is done.
- Results are stored with the run and are **never shown to the agent**. They do not influence the run; a task still counts as done when the agent's own review passes. The gap between the two is part of what the benchmark shows.
- Scoring happens in two fresh containers: the first runs `./setup.sh` and `./build.sh` with network access but without the tests; the second runs the tests with no network at all.
- Results are reported as passed/total per category. There is no weighted total, so a strong category cannot hide a broken one.

Without the private repository (`eval.path` in `benchmark.json`) the harness still works; runs are simply not scored. The usability and the visual design of the UI are judged by hand with the rubric in `acceptance/MANUAL_REVIEW.md`, using the published screenshots.

## Publishing results

Results live in a separate public repository (`results.path` in `benchmark.json`), so this one stays a pure harness.

`package` takes the final committed state of a run and:

1. checks that the source does not contain the run's CLI login token, and refuses if it does;
2. runs `./setup.sh` and `./build.sh` in a fresh container, then lets the product write its screenshots (`./evosim ui --screenshots`) on a virtual display;
3. tests whether `dist/` really is self-contained, by running it on a bare Ubuntu 24.04 with no runtimes and no network;
4. writes `results/<profile>/<track>/<run-id>/` with a readable summary, `report.json`, `source.zip`, `artifact.json` and `screenshots/`, and regenerates the results index.

`publish` commits and pushes the results repository and uploads each executable as a GitHub Release asset (needs the GitHub CLI `gh`). Nothing is pushed until you run it; `--dry-run` shows the commands.

Published are figures, the source the agent wrote, its screenshots, and hidden-test totals per category. Raw CLI logs, the container home and individual check results never leave the run folder.

## Safety

Each run has its own container. The agent is root inside it and may install anything, but it can only see its workspace, a private home directory and the read-only CLI binary. It has outbound internet access and cannot reach services on the host, apart from ports a profile lists in `host_ports`. The host's own CLI binaries are mounted in, so the container runs exactly the CLI version recorded in `run.json`.

The agent does get a copy of the CLI login, and a container is not a VM. [docs/SECURITY.md](docs/SECURITY.md) lists what is and is not protected.

Task specifications, skills, the interface contract and root agent instructions are checked against the originals after every phase and restored if changed.
