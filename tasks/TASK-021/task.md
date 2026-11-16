# TASK-021: Batch runner and export

## Dependencies
TASK-019, TASK-020

## Concrete implementation scope
Sweep parameters and seeds; JSON/CSV aggregation and comparison.

## Acceptance criteria
- At least 2x2 matrix fixture, per-run metadata and reproducible aggregate.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
