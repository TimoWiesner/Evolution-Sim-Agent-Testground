# TASK-016: Animal reproduction

## Depends on
TASK-009, TASK-013, TASK-014, TASK-015

## Goal
Let animals reproduce sexually: two parents, crossed and mutated DNA, real costs.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- Offspring need two different living animals of the same kind that are close to each other, mature, have enough energy and are genetically compatible. An animal never mates with itself.
- The offspring genome is a crossover of both parents plus mutation; both parent IDs and the generation are recorded.
- Reproduction costs both parents energy.
- After reproducing, a parent cannot reproduce again for a waiting time (cooldown or gestation).
- The fertility trait influences the chance or the number of offspring.
- Test: a single animal on its own never produces offspring.

## Ecology ideas
These are ideas from ecology for keeping the food chain going without forced anti-extinction (see `docs/PROJECT.md`). None of them is required and nothing in this section can fail the task; use, change or ignore them. Whether all three kinds coexist over long runs is measured later (TASK-018, TASK-028).

- A minimum energy surplus for mating, so animals reproduce only when food is plentiful.
- Larger litters or shorter cooldowns only in good conditions, smaller ones when energy is low.
- Maturity ages and lifespans that keep generations overlapping instead of rising and dying together.

## Your decisions
Decide these yourself and write down what you chose and why.

- Mate search and mate choice.
- Gestation or immediate birth; litter size.
- The compatibility rule.

## Not part of this task
- Naming and tracking species (TASK-017).
