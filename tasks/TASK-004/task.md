# TASK-004: Grid coordinates and toroidal topology

## Dependencies
TASK-002

## Concrete implementation scope
Implement cell positions, neighbor distances and wrap-aware routing.

## Acceptance criteria
- Border tests for all four edges
- negative and multiwrap coordinates
- rectangular maps.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
