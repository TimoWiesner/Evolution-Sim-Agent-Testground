# TASK-003: Typed configuration and presets

## Dependencies
TASK-002

## Concrete implementation scope
Define validated simulation config, seed, dimensions, traits, species parameters and presets.

## Acceptance criteria
- Malformed configs rejected
- JSON/TOML/YAML roundtrip
- preset fixtures.
- the fixed configuration keys of `docs/CONTRACT.md` section 3 are accepted from JSON, and a file with only those keys is valid
- zero initial populations are accepted

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
