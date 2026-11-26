---
status: accepted
body-hash: d5cdb95abb3b9d79f954c8c1d45e95b9bde63cc024f1242c992530c3fa17e92a
date: 2026-11-05
decision-makers: [owner]
issue: 4787
---

# Owner decisions on what agents may do

## Context and Problem Statement

Five standing owner decisions govern agent authority across the cluster, design questions, project commands, releases, and bot-filed items. Today those decisions sit across `AGENTS.md`, `CONTRIBUTING.md`, ADR 0013, and archived changes. No single record holds all five dates and limits, and `k8s/README.md` previously stated only a read-only agent identity.

## Decision Drivers

- Give refinement, the question resolver, and contributors one stable tracked record with every agent-authority decision, its date, and its limit.
- Avoid duplicating the owner-only list in `AGENTS.md` so one source stays authoritative.
- Keep stable heading anchors (`#decision-1` through `#decision-5`) for automated citations.

## Considered Options

- **One MADR 4 record with dated, limited decisions under `#decision-1` through `#decision-5` and `k8s/README.md` updated**: chosen.
- **Copy the "Only a person" list from `AGENTS.md` into the new ADR**: rejected, because two lists can drift later and spend word budget.
- **Leave decisions distributed across archived changes and contributor docs**: rejected, because automation cannot cite one stable tracked file and anchor with every date and limit.

## Decision Outcome

Chosen option: "One MADR 4 record with dated, limited decisions under `#decision-1` through `#decision-5` and `k8s/README.md` updated", because it gives one canonical anchorable record. The "Only a person" paragraph of [AGENTS.md](../../AGENTS.md) stays the single list of owner-only acts.

### Decision 1

- **Date:** 2026-10-03
- **Decision:** Agents apply manifests, restart workloads, and exercise workloads in the lab cluster.
- **Limit:** The lab cluster only; secrets and hardware stay with the owner. [k8s/README.md](../../k8s/README.md#agent-sessions) records `k8s/agents/` as one read-only identity rather than the limit of agent access.

### Decision 2

- **Date:** 2026-10-22
- **Decision:** Agents decide open design questions with the best-practice answer and report the decision.
- **Limit:** Only an owner-only act in the "Only a person" paragraph of [AGENTS.md](../../AGENTS.md) waits for a person.

### Decision 3

- **Date:** 2026-10-23
- **Decision:** Agents run every project command themselves except release steps.
- **Limit:** All project commands except release steps; release execution remains excluded.

### Decision 4

- **Date:** 2026-10-23
- **Decision:** Agents stay out of releases.
- **Limit:** No release step: an agent never merges the release pull request and never sets `release-now` ([ADR 0013](0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md)).

### Decision 5

- **Date:** 2026-11-05
- **Decision:** Bot-filed work proceeds with an agentic judge and no person.
- **Limit:** Both the issue and the OpenSpec proposal must pass the agentic judge. Text from an outside reply never reaches a `Ready` item with no person.

### Consequences

- Good, because `#decision-1` through `#decision-5` provide stable, grep-searchable citations for roadmap jobs and contributors.
- Good, because naming the "Only a person" paragraph of `AGENTS.md` preserves one source of truth for owner-only acts.
- Bad, because future authority changes must update both the governing rule file and the `Status History` section of this record.

### Confirmation

`uv run devops ci test tests/invariants/test_adr_records.py` validates MADR 4 metadata, length limits, and body hash; `uv run devops docs check` verifies the generated `docs/adr/README.md` index and links across `k8s/README.md`.

## More Information

- [AGENTS.md](../../AGENTS.md) ("Only a person" paragraph)
- [CONTRIBUTING.md](../../CONTRIBUTING.md)
- [ADR 0013](0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md)
- [Cluster documentation Agent sessions](../../k8s/README.md#agent-sessions)
- Issue #4787 and source issue #4780

## Status History

- 2026-11-05: Recorded the five standing owner decisions on agent authority in #4787.
- 2026-11-26: Living detail moved to `k8s/agents/` of dan-petty/homelab (#7290).
