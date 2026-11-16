# TASK-024: UI: run controls and inspector

## Depends on
TASK-020, TASK-022, TASK-023

## Goal
Let the user steer the simulation and look inside any organism.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- Controls for run, pause, single step, reset and speed. A single step advances exactly one tick.
- Reset rebuilds the world from the current configuration and seed and gives the same starting world again.
- Speed has at least three levels and cannot become negative.
- The current tick and the population of each kind are always visible.
- Selecting an organism in the world view opens an inspector with its ID, kind, species, age, energy, health, traits, genome and parents.
- The inspector keeps following the selected organism while the simulation runs and shows when it has died.
- The current state can be saved to and loaded from a checkpoint file in the UI.
- The control logic is covered by tests that need no display.

## Screenshots
Keep `./evosim ui --screenshots DIR` working; you may add an image of the inspector. The benchmark scores this separately and publishes the images. A review records a problem here as a gap but does not fail the task for this point alone.

## Design freedom
Everything in "Must have" is the baseline and decides whether this task passes. Beyond it, the look and feel of the interface is yours to design, and it will be shown publicly next to the interfaces other agents built from the same brief. A plain, tidy interface that meets the baseline is a complete result; nothing in this section can fail the task. Ideas, none of them required:

- How the selected organism is highlighted and how its genome and traits are visualised.
- Feedback and transitions when the simulation state changes.
- Extras such as following an organism with the camera, showing its vision range or its family.

## Your decisions
Decide these yourself and write down what you chose and why.

- Buttons, keyboard shortcuts or both.
- How a genome is presented.

## Not part of this task
- Editing parameters and charts (TASK-025).
