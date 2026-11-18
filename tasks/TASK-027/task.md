# TASK-027: Ecosystem balance

## Depends on
TASK-018, TASK-020, TASK-021, TASK-022, TASK-025, TASK-026

## Goal
Make plants, herbivores and carnivores coexist for as long as possible with natural mechanisms, and show by measurement what works and what does not.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- A baseline is measured with `./evosim batch` before anything is changed: the example configuration of `docs/CONTRACT.md` section 3, which the benchmark also measures (section 7), 10,000 ticks, at least ten seeds; per seed and kind the tick of extinction or survival is recorded.
- The cause of the first extinction in the baseline is analysed from recorded data (which kind dies out first, its causes of death, the population curves of all three kinds) and written down before the first change.
- At least one change to a mechanism, not only to a parameter value, is tried and measured.
- Every trial is recorded with what was changed, what was expected and what was measured, also the trials that did not help.
- The chosen defaults are measured again on at least five seeds that were not used while tuning, and that result is recorded.
- No change breaks the rules of `docs/PROJECT.md` on extinction: organisms come only from the initial population or reproduction, and no rule depends on how many members a kind or species has left. The whole test suite still passes. Recorded regression values (for example state hashes) may be re-recorded with the reason; the must-haves of earlier tasks still hold.
- The performance measurement of TASK-026 is run again with the chosen defaults; the speed still meets the target of TASK-026, or the slowdown is recorded and explained.
- The outcome is stated openly in `docs/BALANCE.md`: how long the three kinds coexisted before and after, whether the goal was reached, and what limits remain.

## Your decisions
Decide these yourself and write down what you chose and why.

- Which mechanisms and parameters to change.
- How many trials to run and when to stop.

## Not part of this task
- Guaranteeing coexistence: this task passes on the points above, whatever the measured outcome. How long the food chain lasts is also measured by the benchmark.
- New features that are not about the ecology; the user interface (only its presets may follow new defaults).
