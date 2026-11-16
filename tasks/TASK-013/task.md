# TASK-013: Animal sensing and movement

## Dependencies
TASK-008, TASK-010

## Concrete implementation scope
Herbivore and carnivore vision, movement, speed, energy costs and toroidal seeking.

## Acceptance criteria
- Movement capped by traits, sensing near borders, occupancy semantics.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
