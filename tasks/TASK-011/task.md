# TASK-011: Plant growth and resources

## Depends on
TASK-006, TASK-008, TASK-009

## Goal
Make plants live off their environment: they grow where climate allows, compete for limited resources, age and die.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- Plants gain energy from the resources of their cell; the gain depends on the cell's current temperature and water.
- Test: the same plant grows more slowly, or not at all, in a cell that is too cold or too dry than in a favourable cell.
- Resources per cell are limited, so plants in the same place compete and growth cannot be unlimited.
- Plants age and die of old age, lack of energy or hostile climate.
- The documentation states where plant energy comes from and what limits it; no energy appears without such a source.
- Genome-derived traits influence growth or tolerance.

## Ecology ideas
These are ideas from ecology for keeping the food chain going without forced anti-extinction (see `docs/PROJECT.md`). None of them is required and nothing in this section can fail the task; use, change or ignore them. Whether all three kinds coexist over long runs is measured later (TASK-018, TASK-028).

- Cell resources (water, nutrients or a single 'fertility' value) that are used up by growth and regenerate slowly up to a cap set by the climate: this gives logistic growth, so plants stop at a carrying capacity instead of exploding or vanishing.
- Growth that slows as a cell gets crowded, so dense patches level off.
- Plants keeping a reserve (roots) that survives grazing, so a grazed plant can regrow.

## Your decisions
Decide these yourself and write down what you chose and why.

- The resource model (light, water, nutrients or a simplification).
- Which plant traits exist.

## Not part of this task
- Reproduction and spreading (TASK-012).
- Being eaten (TASK-014).
