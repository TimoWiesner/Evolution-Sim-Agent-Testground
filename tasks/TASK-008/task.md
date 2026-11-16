# TASK-008: Organisms and life cycle

## Depends on
TASK-005

## Goal
Define what an organism is and the rules of being born, living and dying that all three kinds share.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- Three kinds exist: plants, herbivores, carnivores.
- Every organism has an ID that is unique and never reused, a kind, a position, age, energy, health, its traits, the IDs of its parents and a generation number.
- Traits include at least speed, strength, fertility and maximum lifespan or health, and for animals one behavioural tendency such as aggression or caution.
- Energy and health never leave their valid range. An organism that dies is removed, never acts again and has its cause of death recorded.
- Births and deaths are counted per kind since tick 0.
- Births and deaths that happen in the same tick are handled by one documented rule; tests cover it.

## Your decisions
Decide these yourself and write down what you chose and why.

- The full list of traits and their ranges.
- How organisms are stored.

## Not part of this task
- Genomes (TASK-009).
- Feeding, movement and reproduction behaviour.
