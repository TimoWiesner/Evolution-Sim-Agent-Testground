# TASK-014: Herbivore feeding and behaviour

## Depends on
TASK-011, TASK-013

## Goal
Make herbivores live off plants, with behaviour that depends on their genes.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- Herbivores find plants within their vision range and eat only plants in their own or an adjacent cell, never further away.
- The amount eaten per tick is limited. Energy eaten is taken from the plant, which can die of it, and at most that amount is gained by the herbivore.
- Herbivores lose energy every tick and die when it runs out.
- Climate has a consequence for herbivores, for example a higher energy cost in extreme cold or heat.
- Behavioural genes influence decisions. Test: two herbivores with different genomes act differently in the same situation.

## Your decisions
Decide these yourself and write down what you chose and why.

- The decision rule (for example weighing food against danger).
- The feeding reach, within the limit above.

## Not part of this task
- Being hunted (TASK-015).
- Reproduction (TASK-016).
