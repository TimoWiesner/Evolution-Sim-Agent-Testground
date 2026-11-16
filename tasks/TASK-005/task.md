# TASK-005: Clock, RNG and tick scheduler

## Dependencies
TASK-003, TASK-004

## Concrete implementation scope
Provide isolated simulation state and reproducible tick/order/event pipeline.

## Acceptance criteria
- Seed repeated-run trace test
- stable tie-breaking
- no UI dependency.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
