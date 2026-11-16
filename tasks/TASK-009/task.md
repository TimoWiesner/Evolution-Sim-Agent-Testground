# TASK-009: Genome, inheritance and mutation

## Depends on
TASK-001, TASK-008

## Goal
Give every organism heritable DNA from which its traits are derived, following the genome decision of TASK-001.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- Every organism has a genome; its traits are computed from the genome by a deterministic function and stay within their valid ranges.
- A child genome can be produced from one parent (copy) and from two parents (crossover).
- Mutation has a configurable rate and strength and uses the simulation's generator.
- Test: with mutation rate 0 a child genome contains only parental material; with a rate above 0 differences appear over many offspring.
- A genetic distance between two genomes is defined: zero for identical genomes, symmetric, larger for more different genomes.

## Your decisions
Decide these yourself and write down what you chose and why.

- Genome representation and the mapping from genes to traits.
- Crossover and mutation operators.

## Not part of this task
- Deciding when organisms reproduce (TASK-012, TASK-016).
- Species assignment (TASK-017).
