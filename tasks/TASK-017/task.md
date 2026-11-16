# TASK-017: Species and family tree

## Depends on
TASK-009, TASK-012, TASK-016

## Goal
Recognise species from genetic distance and keep track of how they descend from each other.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- Every organism belongs to a species of its kind, assigned by a documented rule based on genetic distance.
- Species IDs and names are deterministic: the same run produces the same ones.
- A new species arises when a lineage has diverged far enough. A test forces divergence and observes the split; the behaviour exactly at the threshold is tested.
- Each species record keeps its parent species, the tick it arose and, once it has no living members, the tick it went extinct.
- The number of living species per kind can be queried at any tick.

## Your decisions
Decide these yourself and write down what you chose and why.

- The species criterion and its threshold.
- When organisms are re-classified.
- Naming scheme.

## Not part of this task
- Charts and UI display of species.
