# TASK-018: Ecology integration and extinction

## Depends on
TASK-012, TASK-014, TASK-015, TASK-016, TASK-017

## Goal
Join all parts into one running food chain, in which extinction is possible and final.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- One tick runs climate, plants, herbivores, carnivores, reproduction, deaths and species updates in a documented order.
- A simulation started from a configuration with only the fixed keys runs at least 1,000 ticks without errors.
- Organisms are only created as the initial population or through reproduction. A kind that reaches zero stays at zero.
- Scenario tests: without plants, herbivores and then carnivores die out; without herbivores, carnivores die out; plants alone persist.
- For each kind, initial population + births − deaths equals the living population after every tick.
- With the default parameters, plants survive and reproduce on their own, and herbivores with plenty of plants survive and reproduce for several hundred ticks.
- One documented command runs the default parameters for 10,000 ticks with at least five seeds and reports, per seed and kind, the tick at which the kind died out or that it survived; the results are recorded.

## Your decisions
Decide these yourself and write down what you chose and why.

- The order of the steps in a tick.
- Balancing of the default parameters.
- Which stabilising mechanisms the food chain relies on (see `docs/PROJECT.md`) and why.

## Not part of this task
- The command line (TASK-019).
- Guaranteeing coexistence: populations may collapse. Long coexistence of all three kinds is the goal and is measured, but this task passes on the points above (TASK-027 tunes it further).
