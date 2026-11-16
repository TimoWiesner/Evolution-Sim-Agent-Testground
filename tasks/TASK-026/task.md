# TASK-026: Performance measurement and optimisation

## Depends on
TASK-010, TASK-018, TASK-019, TASK-021

## Goal
Measure how fast the simulation is, find out where the time goes, and make it faster without changing what it does.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- One documented command measures ticks per second in a reproducible setup: a fixed configuration that keeps about 2,000 or more organisms alive, a fixed seed, a warm-up and a stated number of measured ticks.
- `docs/PERFORMANCE.md` reports the hardware, the command and the numbers before and after optimisation.
- A profile identifies the most expensive parts; the report names them and what was done about them.
- Target: at least 100 ticks per second at about 2,000 organisms in the benchmark container. If the target is missed, the report gives the measured value, what was tried and the remaining bottleneck.
- Behaviour is unchanged: all existing tests pass, including determinism and checkpoints.
- A test guards against large slowdowns, with a threshold loose enough to be stable on slower machines.

## Your decisions
Decide these yourself and write down what you chose and why.

- What to optimise and how.

## Not part of this task
- New features.
- UI rendering speed.
