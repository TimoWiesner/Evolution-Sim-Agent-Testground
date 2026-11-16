# TASK-018: Extinction and ecology integration

## Dependencies
TASK-012, TASK-014, TASK-015, TASK-016, TASK-017

## Concrete implementation scope
Integrated food-chain loop without artificial repopulation; allow natural extinctions.

## Acceptance criteria
- Plants->herbivores->carnivores scenarios
- starvation/extinction
- no magic reseed.

## Workflow
Three strictly isolated phases: PLAN (inspect actual code and create plan), IMPLEMENT (execute and test plan), REVIEW (independent requirements/code/tests audit). If review fails, repeat starting from PLAN, maximum three cycles. Handoffs go to `tasks/<ID>/handoffs/`. Keep project docs updated. Do not change task specification.
