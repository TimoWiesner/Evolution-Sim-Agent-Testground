# Operator security note

Autonomous coding agents execute arbitrary shell commands, install packages and use the internet. By default the harness therefore runs every agent call inside a rootless Podman container.

## What the container isolates

| The agent can | The agent cannot |
|---|---|
| Read and write its own workspace | See your home directory, this repository or other runs |
| Read and write its private container home (`<run>/home`) | Change the mounted CLI binaries (read-only) |
| Reach the internet (model API, pip, cargo, npm) | Reach services on the host, except loopback ports listed in the profile's `host_ports` |
| Be root inside the container and install packages | Gain root on the host (rootless Podman maps container root to your user) |

## What it does not isolate

- **The CLI login.** Each run gets a copy of the host's login file for its CLI (`~/.claude/.credentials.json`, `~/.codex/auth.json`, or the opencode config). The agent can read that token, and so can anything it sends it to. Use accounts and plans whose limits you are comfortable exposing.
- **Token refresh.** If a provider rotates the token when the container refreshes it, the host login may be signed out. Log in again on the host and pass `--refresh-login` to copy the new login into the run.
- **Your local network.** Other devices on the LAN are reachable like any internet host.
- **Cost.** Nothing in the container limits spending; set `max_cost_usd` / `max_tokens` in `benchmark.json` and watch your plan usage.
- **Kernel-level escapes.** A container is weaker than a VM. For untrusted models with valuable data on the machine, use a disposable VM as well.

`<run>/home` contains credentials. Never publish, zip or commit it. Raw logs in `<run>/logs` may contain sensitive text too.

## Host mode

`--no-container` runs the CLI directly on the host with your user's full access; the workspace is then **not** an isolation boundary. In host mode, `--allow-unsafe` additionally makes Claude skip permission prompts and Codex drop its own sandbox. Use host mode only on a disposable machine.
