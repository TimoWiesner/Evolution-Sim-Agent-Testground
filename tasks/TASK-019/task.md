# TASK-019: Headless simulation CLI

## Dependencies
TASK-003, TASK-018

## Concrete implementation scope
Single config/seed/tick runner with exit status and machine-readable output.

## Acceptance criteria
- No display requirements
- documented CLI invocation
- deterministic result schema.
- `./evosim run` implements the flags, result JSON, determinism and error behaviour of `docs/CONTRACT.md` sections 2, 4 and 5 (checkpoint flags excepted)

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
