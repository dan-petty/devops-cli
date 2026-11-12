# Proposal: Add the resolve, group, split and step rows

## Why

Closes #4792. Tracker #4780 (the issue stewards) adds the rows `resolve`, `group` and `split`, and tracker #5014 (the Service step jobs) adds the rows `watch`, `fix-checks` and `fix-conflict`. No record holds these rows, their bounds, their markers, the semaphore `steward` or the decision point `resolve.question_class`. ADR 0021 lists `stage_ready` as a step of the sweep and has no row that fixes a finished pull request. ADR 0022 and `ServiceRow` have no member for the new rows. ADR 0021 gives two reasons against Argo Events that the upstream source of v1.9.11 does not support.

## What Changes

- ADR 0021:
  - A Status paragraph for the amendment.
  - Six rows in the unit table. `watch` replaces `stage_ready` and `pr_conflicts` in the steps of the sweep.
  - CronWorkflows for `resolve`, `group` and `split`, and the semaphore `steward` in the ConfigMap `roadmap-limits` (engine parts and section 5).
  - A new section 8 with the rules of the new rows and, for each row, the selection, the trigger, the bounds, the marker, the record keys, the idempotency key and the Valkey keys. `push` and `open` are steps inside the unit of their producer. Due marks and the sweep stay the trigger transport.
  - The corrected facts about Argo Events with upstream file and line citations, the decision that stays, and three revisit conditions. The rejected option in Considered Options says the reasons that stay.
- ADR 0022: a Status paragraph, the six rows in section 2, the length rule of a row name (12 characters or fewer, no `repair`), the unit name of a fix unit, and the `ServiceRow` members that the items add.
- ADR 0020: a Status paragraph, the point `resolve.question_class` in the catalogue and the migration list with its own section, and the series count 92 in section 7 and in Considered Options.
- `CONTEXT.md`: the terms "Roadmap step" and "Step job", and a pointer from "Step".
- No spec delta (`skip_specs: true`): the change adds documents only and changes no behavior that a consumer sees. Each item of trackers #4780 and #5014 adds its own delta.

## Capabilities

None.

## Impact

- No behavior change. This pull request applies nothing to the cluster, the ConfigMap or a Secret. The code of each row waits for its own item, and the Service code waits for the "safe and vetted" call of the owner.
- The alternatives check reads the titles, the status notes and the `Considered Options` of the ADRs in force under a cap of 8,192 tokens. The ADRs in force use 8,183 tokens on `origin/main` and 8,183 tokens with this change, so the check leaves no ADR out. The status paragraphs go in the `## Status` sections, which the check does not read, and the changed options keep their token counts. #5049 records that only 9 tokens are left.

## Feasibility

- The unit table, the rule "Only the router and the sweep create units", the engine parts, section 5 and the rejected options were read in ADR 0021 on `origin/main` 87ae9eefa. Line 70 lists `stage_ready` as a step of the sweep, and line 137 rejects Argo Events.
- The row list was read in ADR 0022 section 2. `ServiceRow` in `src/devops_cli/github/repo_ref.py:54` has 7 members and no `BRAIN`. The item that builds a row adds its member.
- The catalogue and the series count were read in ADR 0020 section 7 (60 series) and in ADR 0023 (84 series with the three brain points).
- The rows `stage_ready` and `pr_conflicts` were read in `src/devops_cli/roadmap/run.py:841` and `:865`, and in `k8s/README.md`, Roadmap service steps 18 and 21. The comment marker of `pr_conflicts` is in `src/devops_cli/lang/en/messages.py:3851`.
- The source of Argo Events v1.9.11 (commit d13fde07d944, the newest release, 2026-07-13) was read through `devops gh api`: `pkg/apis/events/v1alpha1/eventsource_types.go:751-758`, `:813-815` and `:849-851`; `pkg/eventsources/sources/github/start.go:228-236` and `:378-380`; `pkg/apis/events/v1alpha1/jetstream_eventbus.go:11-13` and `:90-95`; `pkg/reconciler/eventbus/validate.go:35-36`; `manifests/install.yaml:389-391`.
- The row values of the stewards were read in tracker #4780 and in the body of #4792. The step rows were read in tracker #5014 and in the scope comment on #4792.
- The ADR budget was measured with `adr_of`, `_superseded` and `fit_to_budget` of `src/devops_cli/roadmap/adr.py` over `docs/adr/`, before and after the change.

## Existing Tool Considered

The MADR form that the ADRs of `docs/adr/` use, and the glossary form of `CONTEXT.md`. No build. Each row names its open tool: Argo Workflows CronWorkflows, mutexes and semaphores, the GitHub REST sub-issues and issue dependencies APIs, statsmodels, ruff, `uv lock`, git (`--force-with-lease`, `merge-tree`) and the decision-point registry of ADR 0020. The issue states the cost of the record: about 50,000 tokens and 1.5 hours for the steward rows, and about 0.3M tokens and 0.5 agent-day for the step rows.
