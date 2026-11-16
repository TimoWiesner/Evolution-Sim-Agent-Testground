# TASK-024: UI run controls and inspection

## Dependencies
TASK-020, TASK-022, TASK-023

## Concrete implementation scope
Wire pause/resume/step/reset/speed and entity inspector with genome, traits, energy and species.

## Acceptance criteria
- Single-step advances exactly one tick
- inspect correct ID
- speed nonnegative.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
