# TASK-021: Batch runs and export

## Depends on
TASK-019, TASK-020

## Goal
Run many simulations in one go and compare them.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- `./evosim batch` writes per-seed results and a summary as defined in `docs/CONTRACT.md` section 2
- In addition to seeds, at least one parameter can be varied over several values. A test runs a 2 values × 2 seeds matrix.
- `summary.json` lists every run with its seed, parameters and ticks, and gives aggregates across runs: mean, minimum and maximum of the final population per kind and how often each kind went extinct.
- The summary can also be exported as CSV.
- The same batch run twice gives the same summary, apart from time measurements.

## Your decisions
Decide these yourself and write down what you chose and why.

- How parameter sweeps are specified.
- Whether runs execute in parallel, as long as results stay reproducible.
- Additional statistics.

## Not part of this task
- Charts.
