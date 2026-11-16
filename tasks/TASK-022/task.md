# TASK-022: Savegames and checkpoints

## Depends on
TASK-005, TASK-007, TASK-017, TASK-019

## Goal
Save a running simulation completely and continue it later as if it had never stopped.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- `./evosim run --save/--load` follow `docs/CONTRACT.md`: a resumed run reproduces the `state_hash`, `final` and `totals` of an uninterrupted run
- A checkpoint contains everything: organisms with genomes, world, climate and weather, clock, generator state, species records and the birth/death counters.
- The file carries a format version.
- A missing, damaged, truncated or wrong-version file gives exit status 2 and no result file.
- Tests compare an uninterrupted run with save-and-resume for at least two split points, including a save at tick 0.

## Your decisions
Decide these yourself and write down what you chose and why.

- File format.
- Compression.

## Not part of this task
- Saving and loading from the UI (TASK-024).
