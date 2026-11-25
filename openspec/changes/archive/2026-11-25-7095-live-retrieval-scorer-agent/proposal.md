# Proposal: #7095

## Why

In `#7095`, `docs/TESTING.md` and `docs/ROADMAP_WORKFLOW.md` still assign three non-release commands and verification measurements only to "a person", contrary to ADR 0038 (`#decision-3`: agents run every project command except release steps):

1. `docs/TESTING.md` line 140 limits running `score_gold_set` against live Qdrant and the embedding model in the devcontainer to a person.
2. `docs/ROADMAP_WORKFLOW.md` line 283 limits running the Service work for one item (`devops k8s run-job --template runner`) to a person.
3. `docs/ROADMAP_WORKFLOW.md` line 352 limits measuring the 28-day live-plan merge share to a person.

## What Changes

- Update `docs/TESTING.md` line 140 so agents or contributors run the live retrieval scorer in the devcontainer while keeping CI's offline scorer boundary.
- Update `docs/ROADMAP_WORKFLOW.md` lines 283 and 352 so agents or persons may dispatch manual runner jobs and measure the 28-day live-plan merge share.
- Add regression assertions in `tests/invariants/test_agents_md.py` ensuring the retired person-only phrases do not return.
- Documentation and test changes only (`skip_specs: true`).

## Capabilities

None (`docs` and `tests` only).

## Impact

- Agents can run live retrieval benchmarks, manual runner jobs, and live-plan metrics checks directly under ADR 0038 without waiting for a person.
- Fits in one pull request.

## Feasibility

Confirmed against `origin/main:docs/TESTING.md:140`, `origin/main:docs/ROADMAP_WORKFLOW.md:283,352`, `docs/adr/0038-owner-decisions-on-what-agents-may-do.md#decision-3`, and `tests/invariants/test_agents_md.py`.

## Existing Tool Considered

Uses the existing devcontainer Qdrant/embedding setup, `devops k8s run-job`, `score_gold_set`, and `tests/invariants/test_agents_md.py` without building new tooling or runtime code.
