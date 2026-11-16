# TASK-002: Project bootstrap and quality gates

## Dependencies
TASK-001

## Concrete implementation scope
Create executable skeleton, development scripts, dependency manifest and baseline tests for chosen stack.

## Acceptance criteria
- Clean install/build documented
- CLI help works
- tests run in CI-like command.
- `./setup.sh`, `./evosim` and `./build.sh` exist as defined in `docs/CONTRACT.md` section 1
- `./evosim version` prints the contract JSON after `./setup.sh` in a fresh container
- `./build.sh` produces `dist/evosim` and `dist/evosim version` works

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
