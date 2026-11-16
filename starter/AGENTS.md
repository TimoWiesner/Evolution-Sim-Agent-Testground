# Agent contract

You are implementing Evolution Simulation, a locally runnable grid-world ecological evolution game. Read `docs/PROJECT.md`, `docs/STATE.md`, `docs/ARCHITECTURE.md`, task spec in `tasks/`, relevant `docs/decisions/`, then the *current* phase skill in `.agents/skills/{plan,implement,review}/SKILL.md`.

## Scope and hard rules
- Follow task scope, prerequisites, acceptance criteria and three-phase workflow; never silently skip behavior.
- The phase instruction includes the exact task and handoff file paths. Work only on the current phase. Don't pick unrelated tasks or transition phases yourself.
- Each phase runs in a newly started process with no conversation history. Persist decisions, assumptions, test evidence, follow-up steps and blockers in task-local phase documents. Read them on entry.
- Core simulation language **Python or Rust**. Choose language/framework, spatial lookup algorithm and DNA representation through written ADRs; do not preempt agent freedom. Native desktop or local web UI allowed.
- Grid movement is cell-to-cell; left/right and top/bottom wrap; climate must remain continuous across wrapping boundaries. Plants have DNA, mutation and speciation; herbivores/carnivores have sexual reproduction and heritable behavioral tendencies. Extinctions are allowed.
- Deterministic or seed-based simulation; minor inter-platform differences allowed. UI and headless modes share the same engine. No arbitrary hardcoded population replenishment.
- Add tests, run them, report exact command and result; don't fabricate success.
- Do not modify `AGENTS.md`, `CLAUDE.md`, `.agents/skills/`, task specifications, or benchmark reference checks. Harness owns task states, commits and stage transitions.
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
