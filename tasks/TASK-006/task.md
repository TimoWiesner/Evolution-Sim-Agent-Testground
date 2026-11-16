# TASK-006: Climate zones and biomes

## Depends on
TASK-004, TASK-005

## Goal
Give every cell a climate that resembles Earth's latitude zones and stays continuous on the wrapping world.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- Every cell has a biome, a base temperature and a base precipitation that follow from its position.
- The zones appear in an Earth-like order between cold and hot: polar, tundra, temperate, dry (savanna/desert), tropical.
- There is no seam: across the top/bottom and left/right edges, neighbouring cells differ no more than neighbouring cells elsewhere. A test proves it.
- The documentation explains the compromise made to fit latitude zones onto a world without edges.
- The biome map can be printed or exported for inspection without a UI.
- Works for any world size, including very small worlds.

## Your decisions
Decide these yourself and write down what you chose and why.

- The formulas and the number of zones.
- Additional influences such as noise or elevation, as long as they are seeded.

## Not part of this task
- Change over time (TASK-007).
- Effects on organisms.
