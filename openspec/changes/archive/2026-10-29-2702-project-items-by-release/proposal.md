# Proposal

## Why

Issue #2702: the panel "Items by Milestone" of the Project & Engineering Velocity dashboard groups `devops_cli_project_items` by milestone. A milestone is a planning bucket, not a release. release-please makes each release from `main` and tags it `v*`, so the panel does not tell which release shipped an item.

## What Changes

- `get_item_releases` walks the `v*` tag ranges of the clone, as the release cadence metrics do, and maps each issue that a commit closes with a closing keyword (`close`, `fix`, `resolve` and their forms) to the first tag that holds the commit.
- `devops_cli_project_items` has the label `release` in place of `milestone`. A closed Item has the tag that closed it. An open Item, or a closed Item that no release holds, has an empty `release`.
- The row "Release & Taxonomy Tracking" and the panel "Items by Release" group the gauge by `release` and `state`. The panel shows an empty release as `unreleased`.
- The instrument description and `docs/TELEMETRY.md` name the new label.
- `--milestone` of `devops gh metrics` still limits the Items it counts, and the milestone table of the command stays.
- The change carries a spec delta: the labels of a gauge and the dashboard panels are observable. It fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-metrics-dashboard`: the items gauge and the panel that groups it carry the release in place of the milestone.

## Impact

- Code: `src/devops_cli/github/metrics.py`, `src/devops_cli/telemetry/instruments.py`.
- Dashboard: `k8s/monitoring/dashboards/project-metrics.json`.
- Documentation: `docs/TELEMETRY.md`.
- Tests: `tests/test_github_metrics.py`, `tests/test_telemetry_instruments.py`, `tests/test_roadmap_run.py`.

## Feasibility

- The premise holds. The squash commit of each pull request has the footer `Closes #<issue>`, and release-please copies the closed issues into the release commit of the tag. In a full clone of this repository, a walk of the 92 `v*` tag ranges with `git log --format=%B <prev>..<tag>` maps 566 issues to a tag. For each tag, every issue that the release commit lists as `closes [#<issue>]` is in the map for that range.
- A shallow clone misses the commits of some ranges: in a shallow clone, two tags lost two issues each. The metrics job of the roadmap Service makes a full clone.

## Existing Tool Considered

git itself (`git tag`, `git log`) holds the data, and `get_release_cadence_metrics` already walks the same tag ranges. The GitHub GraphQL field `closedByPullRequestsReferences` gives the closing pull request but not the release, and needs one more API read path. The change adds no library. It deletes the `milestone` label of the gauge and the milestone grouping of the panel.
