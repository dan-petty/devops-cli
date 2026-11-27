# Proposal: #7400

## Why

`devops grafana dashboards lint` read a target with no refId as `A` (`Target.ref_id` defaulted to `A`), so each panel with two or more such targets failed with "Duplicate target refId 'A'; a series will be dropped". Grafana drops no series in that case: when it loads a panel, `PanelModel.ensureQueryIds` gives each target with no refId the next free id. The dashboards that Grafonnet renders state no refId, so the two dashboards of `adinhodovic/argo-workflows-mixin` got 10 false errors, and dan-petty/homelab#524 cannot provision them, because the homelab check runs this lint and DESIGN.md keeps an upstream copy as it is published.

## What Changes

- `Target.ref_id` is empty when a target states no refId.
- `linter.grafana_ref_ids` gives each such target the id of Grafana's `getNextRefId`, and the duplicate check reads those ids.

## Capabilities

- `grafana-dashboard-lint` (modified): a target with no refId gets the id that Grafana gives it.

## Impact

- A dashboard of the repository that states each refId lints as before.
- The overlap check is unchanged: the overview dashboard of the mixin still gets its 2 overlap errors.
- The change fits one pull request.

## Feasibility

- Grafana v12.3.0, `public/app/features/dashboard/state/PanelModel.ts:270`: `ensureQueryIds` sets `query.refId = getNextRefId(this.targets)` for each target with no refId.
- The lint of this branch on the two mixin dashboards at commit c331414: 2 errors (the overlaps), 0 "Duplicate target refId". On `main`: 12 errors, 10 of them "Duplicate target refId 'A'".

## Existing Tool Considered

No library computes Grafana's refIds offline. The rule is a 6-line port of `getNextRefId` in the linter that already exists, about 20,000 tokens and 30 minutes.
