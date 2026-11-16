# Operator review rubric (independent of agent's self-review)

After a full run, assess each aspect on a 0–5 scale using the generated workspace, not the agent's claims.

1. Functional coverage: enumerate task acceptance criteria and demonstrate them.
2. Architecture: separation of simulation core from UI; ADR trade-offs; appropriate genome/spatial model.
3. Correctness: seeded repeatability, toroidal climate boundary continuity, extinction handling and checkpoint fidelity.
4. Performance: independently measure headless ticks/s on 2,000 entities and record CPU/platform.
5. UX: zoom/pan, entity inspection, seed/config controls, speed and step controls.
6. Autonomy/reliability: phase transitions, handoff quality, independent test evidence, recovery frequency.

Document evidence and executable commands in `runs/<agent>/manual-review.json` under operator control. No automatic total score is asserted without independent tests and review.
