# TASK-001: Architecture decision records

## Dependencies
None

## Concrete implementation scope
Evaluate Python versus Rust, UI choice, toroidal neighbor search and DNA design; establish module/API boundaries and three ADRs.

## Acceptance criteria
- ADRs compare >=2 alternatives each
- document reproducibility strategy
- architecture ledger updated.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
