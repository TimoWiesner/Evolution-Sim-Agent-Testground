# TASK-007: Seasons and weather

## Depends on
TASK-006

## Goal
Make the climate change over time: a repeating year and seeded random weather on top of it.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- A year has a configurable length in ticks; temperature and precipitation of every cell follow a seasonal cycle.
- Random weather deviations are drawn from the simulation's generator, so runs with the same seed have the same weather.
- Temperature and precipitation always stay within documented bounds.
- The current temperature and precipitation of any cell can be queried at any tick.
- Test: with weather switched off, one year repeats the previous one exactly.
- Any weather state that carries over between ticks is part of the simulation state.

## Your decisions
Decide these yourself and write down what you chose and why.

- Shape and strength of the seasons, and how they differ between zones.
- The weather model.

## Not part of this task
- Effects on plants and animals (their own tasks).
