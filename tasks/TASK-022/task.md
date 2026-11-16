# TASK-022: Savegames and checkpoints

## Dependencies
TASK-005, TASK-007, TASK-017, TASK-019

## Concrete implementation scope
Serialize complete organisms, genome, world, clock, RNG and climate for restoration.

## Acceptance criteria
- Uninterrupted vs checkpoint-resume statistical consistency
- versioning & invalid-file behavior.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
