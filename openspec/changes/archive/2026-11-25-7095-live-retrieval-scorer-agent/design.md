# Design

## Decisions

- Remove the person-only framing from non-release devcontainer scoring (`docs/TESTING.md:140`), manual runner job invocation (`docs/ROADMAP_WORKFLOW.md:283`), and live-plan merge-share calculation (`docs/ROADMAP_WORKFLOW.md:352`), keeping owner-only gates (`G1`, `G2`, merge, and live cluster config updates) unchanged.
- Record the retired phrases in `_REMOVED_PERSON_STEP_PHRASES` in `tests/invariants/test_agents_md.py` so existing invariant coverage prevents regression.

## Rejected alternatives

- **Also remove "A person merges it" / "Only a person changes these settings in the deployed config" in `docs/ROADMAP_WORKFLOW.md`**: rejected because `AGENTS.md` and ADR 0038 explicitly keep merges (`#decision-4`, `"Only a person"`) and deployed cluster config governance restricted appropriately.
- **Add a new test file instead of extending `tests/invariants/test_agents_md.py`**: rejected because `tests/invariants/test_agents_md.py` already enforces `_REMOVED_PERSON_STEP_PHRASES` across repository workflow documents (`CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`).
