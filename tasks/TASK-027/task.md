# TASK-027: Reliability and delivery

## Depends on
TASK-018, TASK-021, TASK-022, TASK-025, TASK-026

## Goal
Prove that the finished product is robust, and hand it over so that someone else can use it.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- every command and required behaviour in `docs/CONTRACT.md` is verified and the evidence recorded
- `./build.sh` output is self-contained as required by `docs/CONTRACT.md` section 6
- Runs of at least 10,000 ticks complete for at least three seeds without errors; the results are recorded.
- Randomised tests check the invariants over many seeds and configurations: birth/death accounting, value ranges, wrapping, determinism.
- The whole test suite passes with the one documented command.
- `README.md` covers installation, the `run`, `batch` and `ui` commands, the configuration parameters and one command that starts an interesting demo scenario.
- A self-audit lists every requirement of `docs/PROJECT.md` as met, partly met or missing, and the known limitations are stated openly.

## Your decisions
Decide these yourself and write down what you chose and why.

- Where the evidence is recorded (for example `docs/VERIFICATION.md`).
- The demo scenario.

## Not part of this task
- New features. Fix what the checks uncover; record what cannot be fixed.
