# TASK-020: Metrics and evolution analytics

## Dependencies
TASK-017, TASK-018, TASK-019

## Concrete implementation scope
Track timeseries population, births/deaths, diversity, genotype means/distributions and generations.

## Acceptance criteria
- Metric schema tests
- metrics reflect state
- sample export.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
