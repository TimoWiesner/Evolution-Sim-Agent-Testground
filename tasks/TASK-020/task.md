# TASK-020: Metrics and evolution analytics

## Depends on
TASK-017, TASK-018, TASK-019

## Goal
Record what happens over time, so that evolution can be seen in numbers.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- At every sample tick these are recorded: population per kind, births and deaths per kind, deaths by cause, living species per kind, mean and spread of every trait per kind, and the highest and mean generation.
- Recording does not influence the simulation: `state_hash` is the same with and without it.
- The metrics can be written to a file from the command line through a documented option or as additional keys in the result.
- The metrics format is documented.
- Tests check the recorded values against a small world whose numbers can be verified by hand.

## Your decisions
Decide these yourself and write down what you chose and why.

- File format and structure of the metrics.
- Further metrics.

## Not part of this task
- Charts (TASK-025).
- Comparing several runs (TASK-021).
