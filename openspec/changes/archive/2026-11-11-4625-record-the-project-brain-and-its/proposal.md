# Proposal: Record the project brain and its upkeep runs

## Why

Closes #4625. The project brain of tracker #4624 changes the scope of the alternatives check, which #2648 kept to one item. It adds two scheduled runs that the unit table of ADR 0021 does not list, and a new Service row. It also adds durable copies outside the item blocks, and three decision points. No ADR records the cache tiers, the data classes, their durable copies or the shadow rule of these points.

## What Changes

- New ADR 0023. It records these decisions:
  - the project context that the check of one item reads;
  - the local and the shared tier, with their read and write paths;
  - the classes C, S and D, with their durable copies;
  - the runs `brain-daily` and `brain-weekly`, and the Service row `brain`;
  - the canonical tool id, and three decision points in `shadow`;
  - shared caches hold public repositories only, until role ACL users exist;
  - the rejected options and the consequences.
- ADR 0021 gets a note at its top. Its unit table gets two rows in the form of the metrics row, `brain-daily` and `brain-weekly`. Its engine parts name the two CronWorkflows. The rule "Only the router and the sweep create units" stays as it is.
- ADR 0022 gets a note at its top, and section 2 gets the row `brain`.
- ADR 0020 gets a note at its top that names the three new points of the catalogue.
- `CONTEXT.md` defines "Project brain".
- No spec delta (`skip_specs: true`): the change adds documents only and changes no behavior that a consumer sees. Each item of tracker #4624 adds its delta under the nested capability `openspec/specs/project-brain/<area>/spec.md`.

## Capabilities

None.

## Impact

- No behavior change. This pull request applies nothing to the cluster, the ConfigMap or a Secret.
- The alternatives check reads the ADRs in force under a cap of 8,192 tokens. The ADRs in force use 7,416 tokens on `origin/main` and 7,850 tokens with this change, so the check leaves no ADR out.
- No file under `openspec/specs/roadmap-stage/` changes.
- The change fits one pull request.

## Feasibility

- The unit table and the rule were read in ADR 0021 on `origin/main`. The table lists a schedule only for the metrics row and the sweep. The rule "Only the router and the sweep create units" is the first bullet under the table.
- The row list was read in ADR 0022 section 2, and `ServiceRow` in `src/devops_cli/github/repo_ref.py` has no member `brain`. The item that adds the brain template adds the member.
- The shadow rules were read in ADR 0019, rules 4, 6 and 7. The point rules were read in ADR 0020, sections 2, 5 and 7, and its catalogue.
- #2648 was read through `devops gh api`: closed on 2026-10-29.
- `valkey-devops` was read in `k8s/llm/valkey-devops.yaml`: `requirepass` only (the default user), `--maxmemory 96mb` and `--maxmemory-policy allkeys-lru`.
- The repositories of the Service were read in a copy of the live ConfigMap, and the `private` field of each through `devops gh api`: 2 of 7 are private.
- `packaging` 26.3 is in `uv.lock`, so `packaging.utils.canonicalize_name` needs no new dependency.
- The nested layout was read in the pinned openspec 1.14.3, `dist/utils/spec-discovery.js`: the discovery walks `specs/<area>/<id>/spec.md` for listing and for the archive merge.
- The ADR budget was measured with `adr_of`, `_superseded` and `fit_to_budget` of `src/devops_cli/roadmap/adr.py` over `docs/adr/`, before and after the change.

## Existing Tool Considered

The MADR form that the ADRs of `docs/adr/` use, and the glossary form of `CONTEXT.md`. No build. Each decision of the record names its open tool. The tools are Valkey with valkey-py, pybreaker, the SnapshotStore seam of #4552 and the GitHub SBOM export (SPDX purls). The others are `packaging.utils.canonicalize_name`, deps.dev, Argo CronWorkflows and the decision-point registry of ADR 0020. The issue states the cost of the record: about 60,000 tokens and 1.5 hours.
