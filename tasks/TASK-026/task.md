# TASK-026: Performance optimization and profiling

## Dependencies
TASK-010, TASK-018, TASK-019, TASK-021

## Concrete implementation scope
Measure ticks/sec on specified 2k+ entity setup and optimize without behavior regressions.

## Acceptance criteria
- Report hardware, seed, warmup, N ticks
- >=100 ticks/sec target, test and caveats.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
