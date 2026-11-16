# TASK-001: Architecture decisions

## Depends on
None

## Goal
Choose the technology and the core designs before any product code is written, and record why.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- `docs/decisions/` contains one decision record each for: (1) language and runtime of the simulation core, (2) UI technology, (3) neighbour search on the wrapping grid, (4) genome design: representation, inheritance, mutation and the rule that defines a species.
- Each record names at least two realistic alternatives, the choice, and the reasons, covering performance, testability and the self-contained `dist/` folder required later.
- One record or section explains how determinism will be achieved: where random numbers come from, in which order organisms are processed, and what must be avoided (wall clock, unordered collections).
- `docs/ARCHITECTURE.md` lists the planned modules, what each is responsible for and which may depend on which. The simulation core does not depend on the UI.
- No product code is added in this task.

## Your decisions
Decide these yourself and write down what you chose and why.

- Any language, framework or mix that runs in the benchmark container (Ubuntu 24.04 with Python 3, Rust and Node installed; `./setup.sh` may install more).
- Desktop UI or local browser UI.
- The format of the decision records.

## Not part of this task
- Implementing anything.
