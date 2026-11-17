# Agent contract

You are implementing Evolution Simulation, a locally runnable grid-world ecological evolution game. Read `docs/PROJECT.md`, `docs/CONTRACT.md`, `docs/STATE.md`, `docs/ARCHITECTURE.md`, task spec in `tasks/`, relevant `docs/decisions/`, then the *current* phase skill in `.agents/skills/{plan,implement,review}/SKILL.md`.

## Scope and hard rules
- Follow the task's goal, its "Must have" points (the acceptance criteria) and the three-phase workflow; never silently skip behavior.
- The phase instruction includes the exact task and handoff file paths. Work only on the current phase. Don't pick unrelated tasks or transition phases yourself.
- Each phase runs in a newly started process with no conversation history. Persist decisions, assumptions, test evidence, follow-up steps and blockers in task-local phase documents. Read them on entry.
- The technology is your choice: any language or framework that runs in the benchmark container (Python 3, Rust and Node are installed). Choose it, the spatial lookup algorithm and the DNA representation through written ADRs. Native desktop or local web UI allowed.
- Each task lists "Your decisions" and what is "Not part of this task". UI tasks also have a "Design freedom" section: the visual design is yours and cannot fail a task. The plant and animal tasks have an "Ecology ideas" section: suggestions only, which cannot fail a task either.
- Grid movement is cell-to-cell; left/right and top/bottom wrap; climate must remain continuous across wrapping boundaries. Plants have DNA, mutation and speciation; herbivores/carnivores have sexual reproduction and heritable behavioral tendencies. Extinctions are allowed; long coexistence of all three kinds is the goal, reached with the allowed mechanisms of `docs/PROJECT.md`.
- Deterministic or seed-based simulation; minor inter-platform differences allowed. UI and headless modes share the same engine. No arbitrary hardcoded population replenishment.
- Add tests, run them, report exact command and result; don't fabricate success.
- `docs/CONTRACT.md` fixes the product's external interface (`./setup.sh`, `./evosim`, `./build.sh`, configuration keys, result JSON). It is binding and is how the product is evaluated; everything behind it is your design.
- Do not modify `AGENTS.md`, `CLAUDE.md`, `docs/CONTRACT.md`, `.agents/skills/`, task specifications, or benchmark reference checks. Harness owns task states, commits and stage transitions.
- Keep `docs/STATE.md`, `docs/ARCHITECTURE.md`, and ADRs current. Phase handoffs are the primary cross-session memory.
- Ask no interactive questions; make reasonable engineering decisions and document them.

## Local-only Git policy (mandatory)
- Each benchmark agent operates in its own **local** Git repository (this workspace), initialized by the orchestrator. Repositories are independent; no GitHub repository is required for an agent run.
- All commits and history remain on the local machine. **Never run `git push`, `git fetch`, `git pull`, `git clone` to publish or synchronize this workspace, or any Git hosting CLI to upload it.** GitHub/GitLab/etc. are not part of the agent workflow. Dependency retrieval with package managers remains permitted.
- Do not add, change or configure Git remotes (`git remote add`, `set-url`, etc.). `git remote -v` should produce no entries. If any remote exists, stop Git network operations and document the anomaly in the phase handoff.
- The orchestrator owns `git init`, baseline and phase commits. **Do not manually commit, amend, rebase, reset, tag or change branches** unless a phase instruction explicitly authorizes it. You may inspect history (`git status`, `git log`, `git diff`, `git show`) to support planning and review.
- Exactly one phase commit is made by the orchestrator for each completed PLAN, IMPLEMENT and REVIEW phase (including review failures); changes persist across review cycles.
- The benchmark template itself may optionally be hosted on GitHub by the human operator, but agent workspaces must not inherit a remote or publish results. Reports and workspaces remain local by default.
- These rules are agent instructions, **not a security boundary**. The operator must configure OS/network restrictions separately if guaranteed prevention of Git/network publishing is required.
