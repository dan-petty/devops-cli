## Why

Five standing owner decisions about agent authority sit across `AGENTS.md`, `CONTRIBUTING.md`, ADR 0013, and archived OpenSpec changes with no single record holding all five dates and limits. Because no tracked file holds all five together, refinement and question resolution cannot cite one stable source, and `k8s/README.md` still describes `k8s/agents/` as the limit of agent access rather than one read-only identity (Closes #4787).

## What Changes

- Add ADR `0038` (`docs/adr/0038-owner-decisions-on-what-agents-may-do.md`) in MADR 4 form with `status: accepted`, `decision-makers: [owner]`, `issue: 4787`, and matching `body-hash`.
- Record the five standing decisions, their dates, and their limits under `### Decision 1` through `### Decision 5` under `## Decision Outcome`, citing the "Only a person" paragraph of `AGENTS.md` without copying that list.
- Update the `Agent sessions` section of `k8s/README.md` to state Decision 1 and describe `k8s/agents/` as one read-only identity rather than the limit of agent access.
- Regenerate `docs/adr/README.md` to index ADR `0038`.

## Capabilities

### Modified Capabilities

- `adr-records`: Add accepted ADR `0038` documenting owner decisions on what agents may do and update `k8s/README.md`.

## Impact

- `docs/adr/0038-owner-decisions-on-what-agents-may-do.md`
- `docs/adr/README.md`
- `k8s/README.md`
