# Product brief: Evolution Simulation

Build a 2-D raster simulation of climate, plants, herbivores and carnivores. Food availability leads to herbivore reproduction; predation supports carnivores but does not forcibly prevent extinction. Every lineage is subject to heritable traits, mutations, natural selection, and speciation. No pre-scripted equilibrium is required.

## Required behavior
- Finite toroidal grid, cell-by-cell animal movement, wrap-aware perception and spatial lookup. User-configurable dimensions and initial populations.
- Climate resembling latitudinal Earth zones with smooth torus seam, temperature and precipitation; seasons and weather vary over ticks and affect entities. Explain world topology compromise.
- Plants consume environmental resources, grow, reproduce (asexual and/or pollination where applicable), mutate and form species; herbivores eat plants; carnivores eat herbivores. Organisms have traits including speed, strength, health, fertility and genetic behavior (e.g. aggression/risk). Lifespan, energy, nutrition, costs and reproduction controls are scientifically simplified but internally coherent.
- Two-parent sexual reproduction for animals, inherited DNA and mutations; emergent new species via explicit stable species criterion. No forced anti-extinction mechanics.
- Target simultaneous population 1,000–5,000 entities; measured headless goal >=100 ticks/s at 2,000 entities on disclosed reference hardware/setup, not guaranteed universally.
- Same engine for headless CLI and live UI; UI framework is agent choice (desktop or local browser), and so is its visual design beyond the functions listed here; climate-colored map, entity differentiation, pan/zoom, run/pause/reset/step, adjustable speed, inspect an entity.
- Edit initial parameters in UI, built-in presets, import/export JSON/TOML/YAML config (at least one of these), seed control; save/load full simulation state with DNA, RNG and climate.
- Headless multi-seed and parameter batch runs with comparative statistics; visualization for population, births/deaths, diversity, genetic distributions/means and generation trends.
- Unit, integration, regression, property-based and multi-thousand-tick tests; seed-based repeatability. Operator may evaluate manually and using external checks.

## Extinction and stabilising mechanisms
Populations may collapse, and the goal is still a food chain in which plants, herbivores and carnivores coexist for as long as possible. Reach it with ecology, not with rules that override it.

- **Not allowed** ("forced anti-extinction"): creating organisms other than as the initial population or by reproduction; any rule that looks at how many members a kind or species has left (for example "below 10 animals nobody dies", or extra births or protection when a population is small); immortality; energy without a documented source.
- **Allowed and encouraged**: local, natural mechanisms that every organism is subject to at all times, whatever the population size. Examples are cell resources that regenerate up to a limit, density-dependent growth, satiation, a handling time after a kill, hunting success that depends on how easy prey is to find, refuges or cover for prey, migration away from depleted cells, territories and competition among predators, and climate zones that make the world uneven. Evolution may change all of these.
- A mechanism may react to what an organism can perceive or what is in its own cell (food, crowding, danger), never to global counts.

## Agent-owned architecture decisions (not prescribed)
1. Language, runtime, framework and UI technology: anything that runs in the benchmark container (Python 3, Rust and Node are installed).
2. Spatial neighbor-search data structure (must respect torus and grid).
3. DNA structure, inheritance, mutation, speciation protocol.
4. Visual design of the UI. The benchmark publishes screenshots of it (`docs/CONTRACT.md`, `ui --screenshots`).
Write ADRs for 1 to 3 with alternatives, tradeoffs, performance and test consequences.
