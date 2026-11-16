# TASK-025: UI scenarios, presets and charts

## Dependencies
TASK-003, TASK-020, TASK-021, TASK-024

## Concrete implementation scope
UI initial parameter editing, presets, config import/export and charts for genetics & diversity.

## Acceptance criteria
- Roundtrip config
- series and genotype plots
- validation error presentation.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
