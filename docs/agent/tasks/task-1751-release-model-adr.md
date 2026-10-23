# Task: Releases Are Derived by release-please from Trunk, and Milestones Are Planning Buckets (#1751)

**Issue**: [#1751](https://github.com/dan-petty/devops-cli/issues/1751)
**Scope**: type/docs
**Feasibility**: Checked at release/v0.2.39 (3ef69850) on 2026-10-22. The check was offline, except for read-only GitHub reads through `devops gh api`. Every line count is `wc -l` or `git grep` over the tree. Every pull request, issue, run and setting count is a GitHub read. An earlier session measured the release-please, python-semantic-release, `towncrier` and OpenSpec behavior in scratch repositories, and this change did not run those measurements again.

## Description
The release model ran through a `release/vX.Y.Z` branch and a hand-made cut pull request. It then used a release pull request of 188 to 990 files and a publish on the push to `main`. It took 75 to 107 minutes. The decision removes about 14,400 lines of code, tests, workflow and documents. The 33 files that go or change whole hold 13,445 lines.

[ADR 0012](../../adr/0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md) decides that release-please will derive the releases from trunk. Item pull requests will target `main`. The pull request title will be the changelog entry.

Under the decision, a release pull request that the tool opens will carry the version and the changelog. Merging it will publish and create the tag as the last write. Argo CD will follow the semver tags. A milestone will be a planning bucket and not a version.

ADR 0012 supersedes [ADR 0011](../../adr/0011-releases-come-from-trunk-towncrier-uv-and-semver-tags-instead-of-a-bespoke-cut.md). ADR 0011 kept a bespoke prepare workflow, `towncrier` fragments and the milestone title as the version. The owner decided that a formal release orchestrator must derive the versions.

ADR 0012 answers the five questions of the issue. It measures v0.2.36 and v0.2.37 and compares six options. It names what stays custom, with the open tool that it considered for each piece. It decides the 18 points that needed the owner under "Decisions Taken" and orders 14 steps under "Cutover and Sequence".

This pull request is the decision record only. It changes no code, workflow or setting. Nothing in it publishes or deploys.

## Verification
- Line counts: the release path (3,190 lines of source, 4,446 of tests, 467 of `release.yml`). Also the 33 files that the decision deletes or replaces whole (13,445 lines), and the readiness rules in `commands/pr.py` (540 lines at 1464-2003).
- Pull requests: the sizes and times of #1614, #1615, #1719, #1720, #1798 and #1799. The 882 merged pull requests, the 880 conventional titles, the 51 `Part of` pull requests and the 39 merges on 2026-10-21.
- Searches and runs: the newest pull request with a Copilot review is #1283. The title search finds 100 issues and 139 merged pull requests. The 99 `release.yml` runs split 79, 16 and 4. 45 of the 61 runs for `main` are release merges.
- Settings: two rulesets, the merge settings, the Pages source, immutable releases, 47 tags and four milestones with no due date.
- Files: 28 git sources in 27 files under `k8s/argocd`, 53 released sections of `CHANGELOG.md`, and 127 open issues with a `changelog.d` criterion.
- Pins: the commits of `release-please-action` v5.0.0, `create-github-app-token` v3.3.0, `action-semantic-pull-request` v6.1.1, `paths-filter` v4.0.3 and `action-gh-release` v3 match their release tags. `src/index.ts` and `action.yml` at the pinned commit hold what the ADR says.
- Tools: `actionlint` 1.7.12 and `zizmor` 1.30.1 ran on the current `release.yml`. The dates and states of release-please #2851 and #2455, its releases, python-semantic-release and `hatch-vcs` come from GitHub.
- Figures that changed against the first draft: the tip moved, so `release.yml` is 467 lines and the 33 files hold 13,445 lines. Two figures did not reproduce. The ADR removed the `Part of` count of open issues. It replaced the share of `feat` among the latest squash titles with the count at `3ef69850` (8 of 40).
- Figures marked in the ADR: the entry count and note size of the earlier release-please run were not repeated. The counts of lines in the closer code are estimates. The count of 53 files names its exclusions.

## Acceptance Criteria
- [x] The cost of a release is measured on two releases (ADR 0012, Evidence). v0.2.36 took 75 minutes and v0.2.37 took 107 minutes, from the creation of the cut pull request to the end of the publish run. Their release pull requests held 188 and 990 files.
- [x] Each option is compared on owner steps, failure modes and the deploy path. The six options are in "Considered Options". The nine defect clusters of the old model are in Evidence.
- [x] The ADR states the decision and answers the five questions of the issue. It lists the 14 steps that migrate to it in delivery order ("Cutover and Sequence").
- [x] The ADR records no point as open. The 18 points that needed the owner are under "Decisions Taken". Merging the ADR confirms each one, and a later ADR can reverse it.
- [x] ADR 0011 is a superseded record: one first line names ADR 0012 and nothing else in it changes. ADR 0001 has a dated note that points to ADR 0012.
- [x] Every figure in the ADR that names the repository was re-counted against the tree and GitHub on 2026-10-22. Figures that did not reproduce are replaced by figures that do, or marked as estimates or as not repeated.
- Pending a person: create the release GitHub App for this repository only. Set `RELEASE_APP_CLIENT_ID` and `RELEASE_APP_PRIVATE_KEY` in an environment named `release`. `devops gh api repos/dan-petty/devops-cli/environments` then lists `release`.
- Pending a person: run the rehearsal of ADR 0012 in a throwaway copy of the repository. Record what it showed for each of its ten premises. The ADR names the fallback or the stop rule of each premise.
- Pending a person: right after v0.2.39 publishes, set the squash settings to `PR_TITLE` and `PR_BODY`.
- Pending a person: before the Argo CD step merges, set the sync policy of the Argo CD applications `bootstrap` and `cluster` to none.
- Pending a person: set `Static Analysis`, `Tests & Coverage` and `Semantic PR title` as required checks of the `main` ruleset with the strict policy on. `devops gh api repos/dan-petty/devops-cli/rulesets/21466414` then lists the three checks.
- Pending a person: after the release step merges, create the tag ruleset on `refs/tags/v*` with the App as bypass actor. `devops gh api repos/dan-petty/devops-cli/rulesets` then lists a ruleset with target `tag`. If GitHub does not accept the App as bypass actor, record that and restrict only update and deletion.
- Pending a person: after the machinery-deletion step merges, delete the `release` ruleset and the remote `release/v0.2.*` and `chore/open-*` branches. `devops gh api repos/dan-petty/devops-cli/rulesets` then lists no `release`, and `git ls-remote --heads origin 'release/*'` prints nothing.
- Pending a person: find and turn off any automatic Copilot review. Then rename the open milestones to dates or themes, and give them due dates.
- Pending a person: edit the 127 open issues whose criteria name a `changelog.d` fragment. Or accept that the criterion is void.
- Pending a person: read the version in the first release pull request and merge it. Record the wall time, the number of actions and the failed steps beside the figures of v0.2.36 and v0.2.37.
- Pending a person: flip the Argo CD applications `bootstrap` and `cluster` to `>=0.2.0`. Do this after a tag with the constraint exists. `argocd app diff` then shows no change.

## Deliverables
- [x] `docs/adr/0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md`, the first line of `docs/adr/0011-releases-come-from-trunk-towncrier-uv-and-semver-tags-instead-of-a-bespoke-cut.md`, the dated note in `docs/adr/0001-github-is-the-roadmap-source.md`, this task file and `changelog.d/1751.md`.
- Not done: the release App, the `release` environment and the settings in the order of the Cutover. [#1864](https://github.com/dan-petty/devops-cli/issues/1864) tracks them, and a person makes them.
- Not done: Argo CD follows release tags. [#1862](https://github.com/dan-petty/devops-cli/issues/1862) tracks it.
- Not done: the read-only reusable workflow `image.yml` builds, smoke-tests and scans the service image, and `cleanup-devcontainer.yml` goes. [#1858](https://github.com/dan-petty/devops-cli/issues/1858) tracks it.
- Not done: release-please opens the release pull request, and merging that pull request publishes. Topic pull requests target `main`. A rehearsal in a throwaway copy of the repository comes first. [#1861](https://github.com/dan-petty/devops-cli/issues/1861) tracks it.
- Not done: the Argo CD build gate runs in `devops ci` on every change to `k8s/`. [#1860](https://github.com/dan-petty/devops-cli/issues/1860) tracks it.
- Not done: the bespoke release machinery is deleted. [#1863](https://github.com/dan-petty/devops-cli/issues/1863) tracks it.
- Not done: `docs/RELEASE_NOTES.md` and `devops docs compact` go. [#881](https://github.com/dan-petty/devops-cli/issues/881) tracks it.
- Not done: the first release made by release-please is published and its cost is measured, by a person. [#1865](https://github.com/dan-petty/devops-cli/issues/1865) tracks it.
- Not done: the rest of the instructions describe trunk, derived versions and the release pull request. The item does not exist yet, so a person files it through `devops roadmap intake`.
- Not done: the planner identifies a milestone by number, orders it by due date, creates date-titled buckets and closes a delivered bucket. The items do not exist yet, so a person files them through `devops roadmap intake`.
