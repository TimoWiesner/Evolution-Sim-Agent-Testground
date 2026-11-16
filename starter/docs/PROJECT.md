# Product brief: Evolution Simulation

Build a 2-D raster simulation of climate, plants, herbivores and carnivores. Food availability leads to herbivore reproduction; predation supports carnivores but does not forcibly prevent extinction. Every lineage is subject to heritable traits, mutations, natural selection, and speciation. No pre-scripted equilibrium is required.

## Required behavior
- Finite toroidal grid, cell-by-cell animal movement, wrap-aware perception and spatial lookup. User-configurable dimensions and initial populations.
- Climate resembling latitudinal Earth zones with smooth torus seam, temperature and precipitation; seasons and weather vary over ticks and affect entities. Explain world topology compromise.
- Plants consume environmental resources, grow, reproduce (asexual and/or pollination where applicable), mutate and form species; herbivores eat plants; carnivores eat herbivores. Organisms have traits including speed, strength, health, fertility and genetic behavior (e.g. aggression/risk). Lifespan, energy, nutrition, costs and reproduction controls are scientifically simplified but internally coherent.
- Two-parent sexual reproduction for animals, inherited DNA and mutations; emergent new species via explicit stable species criterion. No forced anti-extinction mechanics.
- Target simultaneous population 1,000–5,000 entities; measured headless goal >=100 ticks/s at 2,000 entities on disclosed reference hardware/setup, not guaranteed universally.
- Same engine for headless CLI and live UI; UI framework is agent choice (desktop or local browser); climate-colored map, entity differentiation, pan/zoom, run/pause/reset/step, adjustable speed, inspect an entity.
- Edit initial parameters in UI, built-in presets, import/export JSON/TOML/YAML config (at least one of these), seed control; save/load full simulation state with DNA, RNG and climate.
- Headless multi-seed and parameter batch runs with comparative statistics; visualization for population, births/deaths, diversity, genetic distributions/means and generation trends.
- Unit, integration, regression, property-based and multi-thousand-tick tests; seed-based repeatability. Operator may evaluate manually and using external checks.

## Agent-owned architecture decisions (not prescribed)
1. Python vs Rust, choice of runtime/framework/UI.
2. Spatial neighbor-search data structure (must respect torus and grid).
3. DNA structure, inheritance, mutation, speciation protocol.
Write ADRs with alternatives, tradeoffs, performance and test consequences.
