# TASK-013: Animal sensing and movement

## Depends on
TASK-008, TASK-010

## Goal
Let herbivores and carnivores perceive their surroundings and move through the world.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- An animal perceives the organisms within its vision range, which follows from its traits, also across the world's edges.
- Animals move from cell to cell; the distance per tick is limited by the speed trait.
- Moving costs energy, and moving faster or further costs more.
- An animal heading for a target takes the shortest way, across an edge where that is shorter.
- One documented rule says whether several organisms may share a cell; it is applied everywhere.
- The spatial index is kept up to date. Tests cover sensing and movement at the edges.

## Your decisions
Decide these yourself and write down what you chose and why.

- Movement when nothing interesting is in sight.
- The cell-sharing rule.

## Not part of this task
- What animals do when they reach food, prey or a mate (TASK-014 to TASK-016).
