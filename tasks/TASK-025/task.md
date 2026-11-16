# TASK-025: UI: scenarios, presets and charts

## Depends on
TASK-003, TASK-020, TASK-021, TASK-024

## Goal
Let the user set up their own experiments in the UI and watch evolution in charts.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- A new world can be started from the UI: choose a preset, then edit seed, world size, initial populations and at least five further parameters.
- Invalid input is shown next to the affected field and the simulation does not start with it.
- The configuration can be exported to and imported from a JSON file; export followed by import gives the same configuration.
- Charts that update while the simulation runs: population per kind over time, births and deaths, number of species, and the mean of at least one trait over time.
- A chart shows the distribution of a selectable trait in the current population.
- Charts have axis labels and a legend.
- The configuration and chart-data logic is covered by tests that need no display.

## Screenshots
Update `./evosim ui --screenshots DIR` so that `main.png` shows the finished interface, and add at least one image that shows the charts. The benchmark scores this separately and publishes the images. A review records a problem here as a gap but does not fail the task for this point alone.

## Design freedom
Everything in "Must have" is the baseline and decides whether this task passes. Beyond it, the look and feel of the interface is yours to design, and it will be shown publicly next to the interfaces other agents built from the same brief. A plain, tidy interface that meets the baseline is a complete result; nothing in this section can fail the task. Ideas, none of them required:

- Chart styling and how charts, world view and controls share the screen.
- How presets are presented, for example as cards with a short description.
- Extras such as a species family tree, comparing two trait distributions or exporting a chart as an image.

## Your decisions
Decide these yourself and write down what you chose and why.

- Chart library or own drawing code.
- Which parameters are editable beyond the required ones.

## Not part of this task
- New simulation features.
