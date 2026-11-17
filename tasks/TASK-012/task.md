# TASK-012: Plant reproduction and dispersal

## Depends on
TASK-009, TASK-011

## Goal
Let plants multiply, spread across the world and pass on mutated genomes.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- A plant reproduces only when it has enough energy, and reproduction costs energy.
- Offspring appear within a dispersal distance of the parent, also across the world's edges.
- Offspring inherit the parent genome with mutation; parent ID and generation are recorded.
- No offspring appears where there is no room or no resources for it.
- Plants only come from plants: a world with zero plants stays at zero. A test proves it.

## Ecology ideas
These are ideas from ecology for keeping the food chain going without forced anti-extinction (see `docs/PROJECT.md`). None of them is required and nothing in this section can fail the task; use, change or ignore them. Whether all three kinds coexist over long runs is measured later (TASK-018, TASK-028).

- A seed bank or dormant seeds in the soil that sprout when a cell is free and conditions are good, so grazed-out areas recover.
- Dispersal over several cells, so empty regions are recolonised from neighbouring patches.
- Reproduction that depends on local crowding and resources, not on a fixed rate.

## Your decisions
Decide these yourself and write down what you chose and why.

- Asexual reproduction only, or pollination between two plants as well.
- The dispersal pattern.

## Not part of this task
- Species (TASK-017).
