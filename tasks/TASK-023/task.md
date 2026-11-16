# TASK-023: UI: window and world view

## Depends on
TASK-006, TASK-013, TASK-019

## Goal
Create the user interface and its centrepiece: a live view of the world.

## Must have
The review passes only if every point is met and shown by a test or a recorded command.

- `./evosim ui` starts the interface, as a desktop window or as a local server with a browser page. It drives the same simulation engine as the command line.
- The world view shows every cell coloured by its climate or biome, and the living organisms on top. Plants, herbivores and carnivores can be told apart at a glance.
- A legend explains the colours and symbols.
- The view can be panned and zoomed.
- With 1,000 organisms the view stays usable: it keeps updating several times per second while the simulation runs.
- `./evosim ui --smoke-test` passes as defined in `docs/CONTRACT.md` section 2 on a virtual display
- `README.md` explains how to start the UI.

## Screenshots
`./evosim ui --screenshots DIR` writes `main.png` as defined in `docs/CONTRACT.md` section 2. The benchmark scores this separately and publishes the images. A review records a problem here as a gap but does not fail the task for this point alone.

## Design freedom
Everything in "Must have" is the baseline and decides whether this task passes. Beyond it, the look and feel of the interface is yours to design, and it will be shown publicly next to the interfaces other agents built from the same brief. A plain, tidy interface that meets the baseline is a complete result; nothing in this section can fail the task. Ideas, none of them required:

- Visual identity: colour palette, typography, light or dark appearance.
- How the world is drawn: flat cells, textures, shading, how organisms and their traits are shown.
- Layout of the window and where later controls and charts will live.
- Extras such as a minimap, smooth zooming, map overlays or a day/season indicator.

## Your decisions
Decide these yourself and write down what you chose and why.

- Desktop or browser, and the framework (see the decision of TASK-001).
- How organisms are drawn.

## Not part of this task
- Run controls and the inspector (TASK-024).
- Parameter editing and charts (TASK-025). Leave room for them in the layout.
