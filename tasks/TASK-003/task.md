# TASK-003: Typed configuration and presets

## Depends on
TASK-002

## Goal
Define the simulation configuration: every tunable parameter with a type, a valid range and a default, plus ready-made presets.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- the fixed configuration keys of `docs/CONTRACT.md` section 3 are accepted from JSON, and a file with only those keys is valid
- zero initial populations are accepted
- Every parameter other than the fixed keys has a default value.
- Invalid configurations are rejected with a message that names the offending key: wrong type, missing fixed key, value out of range. Tests cover each case.
- Writing a loaded configuration back to JSON and loading it again gives an equal configuration.
- At least three built-in presets that differ in a meaningful way; each is valid and can be selected by name.

## Your decisions
Decide these yourself and write down what you chose and why.

- Which additional parameters exist and how they are grouped.
- Whether unknown keys are an error or ignored (document it).
- Further file formats such as TOML or YAML are optional.

## Not part of this task
- Using the parameters in the simulation.
- Command-line handling of `run` (TASK-019).
