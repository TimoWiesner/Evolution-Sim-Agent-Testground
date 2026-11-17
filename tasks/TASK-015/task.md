# TASK-015: Carnivore hunting

## Depends on
TASK-013, TASK-014

## Goal
Make carnivores live off herbivores through hunts that can succeed or fail.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- Carnivores pursue herbivores within their vision range and can attack only from the same or an adjacent cell.
- The outcome of an attack depends on the traits of both animals and on chance from the simulation's generator. Test over many attacks: both kills and escapes occur.
- A killed herbivore dies exactly once, with predation as its cause of death, and cannot be eaten twice.
- The energy a carnivore gains is at most the energy its prey had.
- Hunting costs energy whether it succeeds or not; a carnivore without prey starves.

## Ecology ideas
These are ideas from ecology for keeping the food chain going without forced anti-extinction (see `docs/PROJECT.md`). None of them is required and nothing in this section can fail the task; use, change or ignore them. Whether all three kinds coexist over long runs is measured later (TASK-018, TASK-028).

- A handling time after a kill (eating, resting), which limits how many herbivores one carnivore can take.
- Hunting success that drops when prey is scarce or hidden, so rare prey is not hunted to the last animal.
- Cover or refuges for herbivores (for example dense vegetation or some climate zones) where attacks are harder.
- Competition or territories among carnivores, so their density is limited by space as well as by food.

## Your decisions
Decide these yourself and write down what you chose and why.

- The attack formula.
- What happens when several carnivores target the same prey (document it).

## Not part of this task
- Reproduction (TASK-016).
