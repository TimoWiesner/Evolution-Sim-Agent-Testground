# Interface contract (version 1)

This file is owned by the benchmark and must not be modified. It fixes the **outside** of the product so that it can be run, tested and packaged without knowing how it was built. Language, architecture, algorithms, the full configuration format, metrics and the UI remain your decisions.

The benchmark evaluates the product only through the three entry points below. The evaluation runs outside your workspace and you will not see its results, so verify conformance yourself.

## 1. Entry points

Three executable files at the workspace root. All are non-interactive, work from any current directory, and signal failure with a non-zero exit status.

| File | Purpose |
|---|---|
| `./setup.sh` | Installs and builds everything the product needs. Must succeed as root in a fresh benchmark container (Ubuntu 24.04 x86-64 with Python 3, Rust, Node and build tools) given only the workspace and internet access. Idempotent. |
| `./evosim` | Launcher for the commands in section 2. Must work after `./setup.sh` has run once. |
| `./build.sh` | Produces the distributable in `dist/` (section 6). May assume `./setup.sh` has run. |

`./setup.sh` and `./build.sh` may use the network. `./evosim` and `dist/evosim` must work without network access.

The benchmark container also provides a headless browser for browser-based UIs: the command `chromium` (Chromium 131, already set up to run as root in the container). For example, `chromium --headless --window-size=1280,720 --screenshot=out.png URL` renders a page to an image, and `chromium --headless --remote-debugging-port=9222 URL` allows it to be driven by a script. The environment variables `CHROME_BIN` and `PUPPETEER_EXECUTABLE_PATH` point to it. A virtual display is available through `xvfb-run` for desktop UIs.

Tasks introduce these step by step; a command only has to work once the task that owns it is done.

## 2. Commands

### `evosim version`

Prints one JSON object to stdout: `{"name": "...", "version": "...", "contract": 1}`.

### `evosim run`

```
evosim run --config FILE --ticks N --out FILE [--seed N] [--sample-every K] [--save FILE]
evosim run --load FILE   --ticks N --out FILE            [--sample-every K] [--save FILE]
```

- Runs headless; no display may be required.
- `--config FILE`: configuration file (section 3).
- `--seed N`: overrides the seed in the configuration.
- `--ticks N`: number of ticks to simulate in this invocation, `N >= 0`. The simulation always advances exactly `N` ticks, even if every organism is extinct.
- `--out FILE`: where to write the result JSON (section 4). Parent directories exist.
- `--sample-every K`: spacing of the time series in ticks. Default: 1/100 of `N`, at least 1.
- `--save FILE`: write a checkpoint of the complete simulation state after the last tick.
- `--load FILE`: start from a checkpoint instead of a configuration; `--ticks` then counts additional ticks.

### `evosim batch`

```
evosim batch --config FILE --seeds 1,2,3 --ticks N --out-dir DIR
```

Runs the configuration once per seed and writes `DIR/seed-<seed>.json` for each (same schema as `run`) plus `DIR/summary.json` (your own format). Further sweep options are your design.

### `evosim ui`

```
evosim ui [--config FILE]
evosim ui --smoke-test [--config FILE]
evosim ui --screenshots DIR [--config FILE]
```

Starts the user interface. With `--smoke-test` it must, without user input: start the real UI (on the display given by `DISPLAY`, or its local server for a browser UI), create a world, advance at least 10 ticks, render at least one frame, shut down, and exit 0 within 60 seconds.

With `--screenshots DIR` it must, without user input: start the real UI in the same way, create a world, advance at least 100 ticks, write images of the interface into the existing directory `DIR`, shut down, and exit 0 within 120 seconds.

- `DIR/main.png` is required: the complete main view as a user sees it, with the world visible, as a PNG of at least 1280×720 pixels.
- Up to five further PNG files showing other views or states (for example charts or the inspector) are optional; their names are your choice.
- The images must come from the real interface, not from a separate drawing routine.
- Only `./evosim` has to support this option, `dist/evosim` does not. A browser UI can use the container's `chromium` (section 1); anything else it needs is installed by `./setup.sh`.

The benchmark publishes these images next to those of other agents.

## 3. Configuration

`--config` must accept JSON. Other formats are optional. The following keys are fixed; a file containing only these keys is a valid configuration, so every other parameter needs a default.

```json
{
  "seed": 42,
  "world": { "width": 64, "height": 48 },
  "initial": { "plants": 400, "herbivores": 120, "carnivores": 20 }
}
```

- `seed`: integer.
- `world.width`, `world.height`: grid size in cells, integers `>= 1`.
- `initial.*`: number of individuals at tick 0, integers `>= 0`. Zero is valid for any of them.

## 4. Result JSON

`run` writes one JSON object. These keys are fixed; you may add more.

```json
{
  "contract": 1,
  "seed": 42,
  "tick_start": 0,
  "tick_end": 1000,
  "world": { "width": 64, "height": 48 },
  "final": {
    "plants": 512, "herbivores": 97, "carnivores": 14,
    "species": { "plants": 3, "herbivores": 2, "carnivores": 1 }
  },
  "totals": {
    "births": { "plants": 9120, "herbivores": 730, "carnivores": 85 },
    "deaths": { "plants": 9008, "herbivores": 753, "carnivores": 91 }
  },
  "series": [
    { "tick": 0, "plants": 400, "herbivores": 120, "carnivores": 20 }
  ],
  "state_hash": "9f2c...",
  "elapsed_seconds": 4.2,
  "ticks_per_second": 238.1
}
```

- `tick_start`, `tick_end`: absolute ticks; `tick_end = tick_start + N`. A run from a configuration starts at 0.
- `final`: living individuals and living species per kind at `tick_end`.
- `totals`: cumulative since tick 0, including ticks before a loaded checkpoint. For each kind, `initial + births - deaths = final`.
- `series`: living individuals per kind at `tick_start`, then every `K` ticks, and at `tick_end`; ticks ascending without duplicates.
- `state_hash`: lowercase hex digest of the complete simulation state at `tick_end` (all organisms with genomes, world, climate, clock, random generator state). Equal states give equal hashes; different states give different hashes.
- `elapsed_seconds`, `ticks_per_second`: wall-clock measurements of the simulation loop, excluding start-up.

## 5. Required behaviour

1. **Determinism.** On the same machine and build, the same configuration, seed and ticks give identical `final`, `totals`, `series` and `state_hash`. Different seeds give different `state_hash` values.
2. **Checkpoints.** Running `A` ticks with `--save`, then `--load` and `B` more ticks, gives the same `final`, `totals` and `state_hash` as one uninterrupted run of `A + B` ticks.
3. **No replenishment.** A kind whose count reaches zero stays at zero. With `initial.plants = 0`, herbivores and then carnivores die out.
4. **Errors.** Invalid arguments, an unreadable or invalid configuration (wrong type, missing fixed key, value out of range) or an invalid checkpoint give exit status 2, a message on stderr and no result file. Success is exit status 0; extinction is not an error.
5. **Clean output.** Nothing but the documented JSON is printed to stdout by `version`; logs go to stderr.

## 6. Distributable

`./build.sh` creates `dist/evosim`, an executable that accepts the same commands as `./evosim`. It may sit next to supporting files inside `dist/`. The `dist/` folder must be self-contained: copied to a plain Ubuntu 24.04 x86-64 system with no language runtimes or project dependencies installed, `dist/evosim version` and `dist/evosim run` must work. Do not commit `dist/`.

## 7. Demo scenario

`scenarios/demo.json` is a configuration (section 3) that `run`, `batch` and `ui --config` accept; the demo command in `README.md` uses it. It is required once the task that owns it is done.

The benchmark runs it for 10,000 ticks with several seeds (`--seed`) and records how long plants, herbivores and carnivores coexist in it. It does the same with a fixed configuration that contains only the keys of section 3, so your default parameters are measured too. Collapse is allowed and is not an error (section 5.4, no forced anti-extinction); a food chain that lasts longer compares better.
