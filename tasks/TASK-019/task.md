# TASK-019: Headless command line

## Depends on
TASK-003, TASK-018

## Goal
Make the simulation usable from the command line and produce the result file the benchmark reads.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- `./evosim run` implements the flags, result JSON, determinism and error behaviour of `docs/CONTRACT.md` sections 2, 4 and 5 (checkpoint flags excepted)
- It runs without a display.
- Exactly the requested number of ticks is simulated, also after everything is extinct; `--ticks 0` is valid.
- Errors give exit status 2, a message on stderr and no result file.
- `state_hash` covers the complete simulation state, so any difference in state changes it.
- An end-to-end test calls `./evosim run` twice with the same seed and compares the results. `README.md` shows an example call.

## Your decisions
Decide these yourself and write down what you chose and why.

- Additional flags and additional keys in the result.
- The hash function.

## Not part of this task
- `--save` and `--load` (TASK-022).
- `batch` (TASK-021).
