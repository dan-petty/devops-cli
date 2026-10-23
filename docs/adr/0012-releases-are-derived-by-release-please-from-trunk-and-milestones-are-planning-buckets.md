# Releases are derived by release-please from trunk, and milestones are planning buckets

ADR 0012 supersedes [ADR 0011](0011-releases-come-from-trunk-towncrier-uv-and-semver-tags-instead-of-a-bespoke-cut.md). ADR 0011 kept a bespoke prepare workflow, `towncrier` fragments and the milestone title as the version, because the repository already used those conventions. The owner decided that a formal release orchestrator must derive the versions.

Releases used to run through a `release/vX.Y.Z` integration branch. Topic pull requests merged into it. A cut commit (version, changelog, roadmap) reached it through its own pull request. A release pull request carried the branch to `main`. `release.yml` published on the push to `main`. [#1751](https://github.com/dan-petty/devops-cli/issues/1751) asked whether that model is right.

Measured on v0.2.36 and v0.2.37, the model costs two hand-made pull requests and 75 to 107 minutes. The span runs from the creation of the cut pull request to the end of the publish run. The release pull requests held 188 and 990 files. That is more than a person can review as a diff.

The release path is 3,190 lines of source, 4,446 lines of dedicated tests and 467 lines of workflow. It also holds a share of the 540 lines of pull request readiness rules. The 33 files that this decision deletes or replaces whole hold 13,445 lines. Since the first tag on 2026-08-17, 47 commits changed them. Those commits added 17,950 lines and deleted 4,505 lines.

A title search on 2026-10-22 finds 100 issues and 139 merged pull requests that name a release, changelog, cut or fragment. 97 of those pull requests carry the scope `release`. 49 of the 97 are fix, chore, refactor or docs pull requests that tend the release path. They are not releases.

Eight of the nine defect clusters below come from custom code. The project built its own branch topology, closer, changelog collector, notes compactor, cut and tag logic. An open tool or a GitHub feature does each of these jobs.

ADR 0011 kept three conventions of this repository as reasons to keep custom code. They are the changelog fragments, the milestone title as the version, and `v0.2.N` as the series. The owner withdrew that reasoning. A project convention is never a reason to keep custom code. The convention changes.

The series is one of those conventions. So no rule of the release path depends on a version. The tool derives each version from Conventional Commits under Semantic Versioning. A `feat` can make the next release `0.3.0`. `1.0.0` comes when the owner says so.

Every other internal thing could change as well. This decision weighed each one that way. These things could change: the fragments and their rule, the `CHANGELOG.md` house style, `docs/ROADMAP.md` and `docs/RELEASE_NOTES.md`. They also include the version naming of milestones, the `release/vX.Y.Z` branch and the closure comment. The last group is pull request titles and bodies, the squash settings, the rulesets, the labels and the readiness checks. Six points are fixed:

- GitHub is the host.
- Agents never merge or push to `main`.
- Telemetry stays off.
- Tools are pinned with hashes.
- Tests run offline.
- The service image is built, scanned, attested and published. Argo CD never rolls the cluster to an unpublished image ([#1451](https://github.com/dan-petty/devops-cli/issues/1451)).

The roadmap Service jobs are planning automation. They stay separate and suspended ([#1562](https://github.com/dan-petty/devops-cli/issues/1562)).

## Decision

Pull requests target `main`. [release-please](https://github.com/googleapis/release-please) derives the next version from the Conventional Commit titles that merge to `main`. It runs in manifest mode, for one Python package at the repository root. The workflow runs it as `googleapis/release-please-action` v5.0.0, pinned by commit `45996ed1f6d02564a971a2fa1b5860e934307cf7`. The tool writes `CHANGELOG.md`. It opens one release pull request and keeps it current.

A person squash-merges that pull request. The merge makes the workflow create a draft release. The workflow then builds, scans, attests and pushes the images. It uploads the assets and publishes the draft. Publishing creates the tag as the last write.

Argo CD follows the semver tags for manifests. Argo CD Image Updater keeps rolling the image digest. The repository keeps no prepare workflow, no `towncrier`, no fragment handling, no version logic and no cut.

- **Branches and cuts (#1751 question 1).**
  - Topic pull requests target `main`. `Closes #N` closes the issue when the pull request merges, as GitHub does for any pull request into the default branch. There are no `release/*` branches, no cut, no cut pull request and no release pull request made by hand.
  - A release is the merge of one pull request. That pull request is `chore(main): release <version>` from `release-please--branches--main`. The release workflow opens and updates it with an App token.
- **Versions and changelog (question 2).**
  - The tool derives the version. It reads the squash subjects, which are the pull request titles. It applies Semantic Versioning with `bump-minor-pre-major`. Before `1.0.0`, a `feat` and a breaking change raise the minor. A `fix`, `perf` or `refactor` raises the patch. `docs`, `test`, `build`, `ci`, `chore` and `style` release nothing alone.
  - A `Release-As: X.Y.Z` paragraph in a pull request body forces a version. This is how `1.0.0` happens. The pull request title is the changelog entry. Only the release pull request edits `CHANGELOG.md`, `.release-please-manifest.json` and the version lines of `pyproject.toml` and `uv.lock`. This decision deletes `changelog.d` and the `Part of` rule.
- **Milestones (question 3).**
  - A milestone is a planning bucket. A due date or a theme names it. Its number identifies it and its due date orders it. It is not a version.
  - Nothing releases when it empties. No scope rule keeps an item of a later bucket off `main`. Whatever is on `main` ships in the next release. A bucket closes when every issue in it is closed.
- **The tip (question 4).** Every pull request runs the suite. The strict required-checks policy makes the merged tree the tested tree. The release pull request runs the same required checks. `devops ci` gains `uv build` beside `uv lock --check`. The decision does not rely on a merge queue.
- **Effort (question 5).** The new flow is two actions for a person: read the release pull request, then merge it. The evidence below gives the old figures.
- **Deploy path.**
  - Two reusable workflows build the service image. CI runs `image.yml` read-only. The release runs `image-publish.yml`, which pushes by digest, attests and tags before the release exists.
  - Argo CD applications read manifests from the highest semver tag at or above `0.2.0`, with no upper bound. Image Updater keeps rolling the digest of `service:latest`. That digest moves only at publish.
- **Review.** No pull request gets an automatic Copilot pass. A person requests one on any pull request into `main`. The Copilot pass budget and the thread-filing command existed for the release pull request alone. This decision deletes them.
- **Archive.** The OpenSpec archive ([ADR 0010](0010-openspec-is-the-spec-and-change-proposal-layer.md)) happens in the pull request that closes the issue, as its last commit. It no longer happens at a cut. [#1846](https://github.com/dan-petty/devops-cli/issues/1846) records the owner's decision of 2026-10-22 and edits ADR 0010.
- **Pages.** GitHub Pages keeps its legacy build of `main:/docs`. Documentation goes live when its pull request merges.

## Evidence

Counts of lines, files and tests come from the tip of `release/v0.2.39` (commit `3ef69850`) on 2026-10-22. Counts of pull requests, issues, runs and settings come from GitHub on the same day.

- **Cost of two releases.**
  - v0.2.36: 25 pull requests merged into `release/v0.2.36`. The hand-made cut pull request #1614 (28 files) was open 56 minutes. The release pull request #1615 (188 files, 25 commits, +12,791/-2,949) was open 62 minutes. The publish run took 12.4 minutes. So 75 minutes passed from the creation of the cut pull request to the end of the run.
  - v0.2.37: 54 pull requests. Cut #1719 (39 files) was open 85 minutes. Release pull request #1720 (990 files, 54 commits, +31,843/-18,003) was open 89 minutes. The publish run took 14.7 minutes. The total was 107 minutes.
  - The release pull request of v0.2.37 ran item-only checks for over 20 minutes until #1721 and #1723 scoped them. A person made its cut by hand, because the Argo CD report's tokens expired during the close.
  - Every cut from v0.2.36 on was a hand-made pull request (#1614, #1719, #1798), because the roadmap Service is suspended (#1562). v0.2.38 merged twice. Its release pull request is #1799 (582 files). Its cut, retargeted at `main`, is #1798 (549 files). They merged 27 seconds apart.
- **Publish runs.** Between 2026-08-17 and 2026-10-21, `release.yml` ran 99 times. 79 runs succeeded, 16 failed and 4 ended as cancelled. 61 runs were for a push to `main`. 16 of those 61 runs came from merges that were not releases, because the workflow runs on every push to `main`. Releases came 15 times between 2026-10-01 and 2026-10-21 (v0.2.24 to v0.2.38).
- **Scale.** `main` holds 60 commits. 45 of them are `feat(release): vX.Y.Z` squashes. The repository has 882 merged pull requests. A release branch squashes into one commit.
- **Tokens.** The repository, the issues and the runs do not show the tokens spent on the release path, so this decision claims none. Lines, pull requests and minutes stand in for them.
- **Cluster 1, integration-branch topology.**
  - GitHub closes issues only for pull requests into the default branch. So the project wrote `roadmap/close.py` (618 lines) to close items and comment. Parts of three other files serve it: about 80 lines in `request_plan.py`, about 60 in `run.py` and about 70 in `commands/roadmap.py`. We estimated these by reading the functions that call the closer. No tool counted them.
  - The model needed sync pull requests (#1258, #1259) and closure fixes after the milestone closed or an item reopened (#1362, #1414, #1417). It needed generated-notes workarounds (#332, #383, #393, #394) and readiness rules for the `chore/open` and `chore/cut` pull request kinds (#1344). A retargeted cut merged beside its release pull request (#1798, #1799, #1802).
  - Trunk removes the cause. Items are already on `main`, `Closes #N` closes natively, and `close.py` has no input.
- **Cluster 2, changelog authoring.** Every pull request used to edit `CHANGELOG.md`. It conflicted three times in one hour in v0.2.25 (#933). Fragments and a home-grown collector fixed that. They also created two writers, ordering hazards and late fragments (#863, #1450, #1792, #1802, #1099, #1102, #1293, #1340, #1355, #1105). With the title as the entry there is one writer, release-please, and no file for an author to forget.
- **Cluster 3, release-notes size.**
  - The v0.2.25 section is 199,004 characters. The limits are 125,000 for a Release and 65,536 for a pull request body. It is the only one of 53 released sections over the pull request limit. No later section is longer than 38,140 (v0.2.29).
  - Notes built from titles are short. At `3ef69850` the 32 releasable titles among the 40 latest squash titles hold 3,257 characters. A release-please run on an earlier tip wrote 7,600 characters for 25 entries, with links. That run was not repeated at `3ef69850`.
  - For a body over 65,536 characters, release-please writes the notes to an extra branch, `<head>--release-notes`, with no pull request. It does not handle the Release limit of 125,000 (#1097, #1105, #140).
- **Cluster 4, release pull request body and epics.** A `gh` query generated the body once, at the cut. It fell out of date after every post-cut fix (#1020, #1346). Code kept 15 Release Epic issues in step. The project later deleted that code (#928). release-please now regenerates the body on every push to `main`.
- **Cluster 5, the cut pushing to protected branches.** The cut pushed to `release/*` under a ruleset bypass or a local credential helper. GitHub refused it with GH013 (#1280, #1124). The cut then moved to its own pull request (#1628). Later defects came from the environment and the timing of the cut (#1397, #1544, #1638, #1343). The App opens a pull request from a branch that neither ruleset matches.
- **Cluster 6, service image tag and order.** Argo CD rolled a pod onto an image that did not exist yet (#1451, #1260, #1486). Image Updater already fixed the pin (#1485, #1486). The order of the tag, the image and the cluster remains. The release workflow fixes it, because the tag is its last write.
- **Cluster 7, tag and publish semantics.** The old workflow tolerated an existing tag until #1805, when it rebuilt the assets of v0.2.37 from the code of v0.2.38. Now publishing the draft creates the tag, so it cannot exist before the workflow attests every image. No workflow runs on a tag.
- **Cluster 8, a green pull request does not mean publishable.** Eight of 45 release-merge runs failed and two ended as cancelled (#1425, #1651, #1544, #1721, #1723, #842). The release pull request now runs the same required checks as every other pull request. They include `uv lock --check`, `uv build` and the image verify job.
- **Cluster 9, the admission engine** (`roadmap/reprioritize.py`, 3,316 lines) is project policy, not release mechanics. No open release tool plans scope. The engine stays. It loses every notion of a version.
- **Settings read on 2026-10-22.**
  - A user account owns the repository. It has two rulesets. `main` has a pull request rule (squash only), CodeQL code scanning, code quality and a 90 percent coverage rule. Its required-status-checks rule has the strict policy and an empty list. It has no bypass actor.
  - `release` matches `release*/**/*` and has one user as bypass actor. There is no tag ruleset. Neither ruleset has an automatic Copilot review rule.
  - Merge settings allow squash, merge and rebase, with `COMMIT_OR_PR_TITLE` and `COMMIT_MESSAGES` as the squash defaults. GitHub Pages builds legacy from `main:/docs`. Immutable releases answer `enabled: false`.
  - 47 tags exist. 44 are `vN.N.N` and 3 are `backup/*`, which are not semver. The four open milestones have no due date.
- **release-please, run offline on this repository.**
  - The exact configuration of the Design section ran against release-please 17.11.2 and against 17.6.0, which is the version the pinned action bundles. It ran on a clone of `release/v0.2.39`, with a tag `v0.2.39` for the end of the old pipeline.
  - The 40 latest squash titles of that clone parse with no failure and give 25 entries: 7 `feat`, 9 `fix`, 1 `perf` and 8 `refactor`. The clone was an earlier tip, and nobody recorded its commit. At `3ef69850` the 40 latest titles hold 8 `feat`, 10 `fix`, 1 `perf`, 13 `refactor`, 6 `docs` and 2 `test`. The run was not repeated there. A window of only `docs`, `ci`, `chore`, `test` or `style` commits opens no release pull request.
  - A `fix`, `perf` or `refactor` gives the next patch. A `feat` gives the next minor. A `feat!`, or a `BREAKING CHANGE:` paragraph even on a `fix`, gives the next minor and never `1.0.0` by accident. A `Release-As: 1.0.0` paragraph, even on a `chore`, gives `1.0.0`. From `1.0.0` the pre-major setting has no effect.
  - The pull request is titled `chore(main): release <version>`. It comes from `release-please--branches--main` and has the label `autorelease: pending`. It changes `pyproject.toml:7`, the `devops-cli` entry of `uv.lock`, `CHANGELOG.md` and the manifest.
  - The JSONPath `$.package[?(@.name.value=='devops-cli')].version` finds the line in `uv.lock`. `src/devops_cli/__init__.py` does not change, because it calls `get_version()`. The tool reads the commit list from GitHub, not from a local checkout. So a shallow or tagless runner cannot corrupt a version.
- **Draft release and the two halves of the action.**
  - With `draft: true`, the tag becomes the last write. The action calls `createReleases()` and then `createPullRequests()` in one run (`src/index.ts` at the pinned commit, blob `480dd3e4`). The tag does not exist yet when the second call runs.
  - On the clone, the release pull request merged with no tag. Then the second call proposed `chore(main): release 0.4.0` with 79 entries and the compare link `v0.3.0...v0.4.0`. It did so on both versions. A fix merged after a failed publish gave 80 entries. With the tag present, the second call proposed nothing.
  - The action has an input for each half, `skip-github-pull-request` and `skip-github-release` (`action.yml` at the pinned commit). So the workflow runs the action twice, and the second run comes after the tag exists.
- **Recovery from a failed publish.**
  - Deleting the draft is not enough. The manifest on `main` already names the unreleased version, so the next proposal builds from it.
  - What works is to undo the release commit with `git revert --no-edit <merge sha>` in a pull request titled `chore: undo the unpublished release <version>`.
  - On the clone, three steps ran: that revert, an unrelated change to the same files, and a fix. The next pull request was `release 0.3.0` again. It had the commits since the last tag.
- **The pinned action bundles an older release-please.**
  - Release-please-action v5.0.0 (2026-04-22) bundles release-please 17.6.0. The library is at 17.11.2 (2026-08-24).
  - [Release-please #2851](https://github.com/googleapis/release-please/pull/2851) merged on 2026-07-17, and 17.10.4 first released it. It writes `refs [#N]` where the notes said `closes [#N]`. The comment in `changelog-notes/default.js` gives the reason: "to prevent GitHub from automatically closing referenced issues when the release PR is merged".
  - The bundled 17.6.0 writes `closes [#N](url)`. So the merge of the release pull request may close an issue that a person reopened after its pull request merged. Nobody verified whether GitHub reads a markdown link after `closes` as a closing keyword.
- **Dependency prefixes.** Renovate's `commitMessagePrefix` is `chore(deps):`, and its `dockerfile` manager covers the base of the service image. `chore` is a hidden type. A `chore(deps)` commit gave no release pull request. A `fix(deps)` commit gave the next patch. So a security bump of a runtime dependency or of the base image releases nothing unless its title is `fix(deps)`.
- **python-semantic-release, run offline.**
  - Version 10.7.0 derives the same versions and ran a two-phase flow. It has no pull request mode (no match in its source or documentation). Its remedy for a protected branch is an administrator token, which the rule against pushes to `main` forbids.
  - So we must write the glue that opens and updates the pull request. release-please gives that glue for free.
  - Experiments found five traps. A depth-1 checkout without tags silently prints `0.1.0`. Its GitHub Action is an unpinned Docker image, which fails the hashes rule. It has one main maintainer, and a 202-day gap between releases (2025-12-14 to 2026-07-04).
- **The notes are titles.** The 52 entries of v0.2.38 have a median length of 270 characters as fragments. The 52 pull request titles merged into `release/v0.2.38` have a median of 82. This loss is real, and the decision accepts it.
- **OpenSpec archive.**
  - OpenSpec 1.14.3 ran in scratch repositories. Archived one after another at a cut, two text-only `MODIFIED` deltas to one requirement silently keep only the later text. Archived in each pull request, the same collision is a git conflict in the pull request where the author can fix it.
  - Four branch pairs rebased. Modify and modify conflict. Add and add to one capability conflict. Modify and add are clean in both orders. A conflict where both sides only appended is spurious.
  - Archiving again after a rebase gave a result byte-identical to a serial archive.
  - Code that orders archives at a cut merged in #1868, under ADR 0010. It holds `archive_sequence` in `src/devops_cli/openspec/archive.py` and the rehearsal of the cut in `src/devops_cli/openspec/gate.py`. This code goes.
  - The overlap check in `src/devops_cli/openspec/overlap.py` merged in #1868 too. It is not cut-time code. It reads `openspec show --json --deltas-only` for each active change, archives nothing and reads no git history. It stays until OpenSpec ships its own check.
- **Couplings of the roadmap code to a version.**
  - `roadmap/store.py` treats a milestone as a Release only when its title parses as a version (`is_release_title`). A title such as `2026-11-05` or `Q4 hardening` is no Release. `parse_release_version` raises `InvalidVersionError` for it.
  - `reprioritize.py` names the next patch (`_patch_bump`, `_next_release`, `_planned_titles`, `nearest_planned_release`). `roadmap/document.py:37` carries a `vX.Y.Z` regular expression.
  - 127 open issues have an acceptance criterion that names a `changelog.d` fragment. 161 open issues name `changelog.d` in their body.
- **Copilot and the closing-keyword parser.**
  - `copilot_budget.py` (216 lines) reads `release_copilot_passes`. `review_thread_issues.py` (377 lines) files the review threads of the release pull request. Both call `pr_branches.require_open_release_pr`, which refuses any pull request but the open release pull request.
  - `github/issue_closure.py` (121 lines of regular expressions and fence handling) re-implements the closing-keyword rules of GitHub. Items used to target a release branch, where GitHub ignores them.
  - The GitHub GraphQL schema has `PullRequest.closingIssuesReferences`, `Issue.closedByPullRequestsReferences` and `ClosedEvent.closer`.
- **Tools run or read.**
  - Run on the repository or in scratch: release-please 17.11.2 and 17.6.0, python-semantic-release 10.7.0, uv 0.12.23, towncrier 26.9.0 and git-cliff 2.14.2. Also run: commitizen 4.19.2, hatch-vcs 0.5.0, OpenSpec 1.14.3, conftest 0.71.1, actionlint 1.7.12, zizmor 1.30.1 and dorny/paths-filter v4.0.3.
  - Read from source and documentation, not run: `googleapis/release-please-action` v5.0.0, `actions/create-github-app-token` v3.3.0, `softprops/action-gh-release` v3 and `amannn/action-semantic-pull-request` v6.1.1. Also read: the tag resolution of Argo CD and the ruleset documentation of GitHub. Argo CD resolves tags in `util/versions/tags.go` with Masterminds semver. That library accepts the `v` prefix and ignores tags that are not semver.
  - `softprops/action-gh-release` finds a draft by tag, uploads, keeps the body of the draft and publishes it.
  - The pinned commits of `release-please-action` v5.0.0, `create-github-app-token` v3.3.0, `action-semantic-pull-request` v6.1.1, `paths-filter` v4.0.3 and `action-gh-release` v3 match their release tags (GitHub API, 2026-10-22).

## Design

- **Item pull requests.**
  - An item pull request targets `main`. Its title is a Conventional Commit and is the squash subject. Its body says `Closes #N` for the one issue it delivers. The body can hold footers that the author writes on purpose: a `BREAKING CHANGE:` paragraph, or a `Release-As:` paragraph. The pull request template has neither.
  - An item is one issue and one pull request. A person splits an issue that is too large for one pull request into sub-issues first. This decision retires `Part of #N`. 51 of 882 merged pull requests used it, for 23 issues.
  - There is no fragment, no `CHANGELOG.md` edit and no version edit. The required checks are `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, with the strict policy kept.
- **Title lint.**
  - `amannn/action-semantic-pull-request` v6.1.1 (commit `48f256284bd46cdaab1048c3721360e808335d50`) runs on `opened`, `edited`, `synchronize` and `reopened` for pull requests into `main`. It uses its default types, which equal the types of the release configuration. The job has the name `Semantic PR title` and is a required check.
  - release-please drops without a warning a title that is not conventional. It also drops the revert-button title of GitHub, `Revert "feat(a): y"`. The lint keeps entries from vanishing. A revert is titled `revert(a): y`.
- **Merge settings.** `squash_merge_commit_title: PR_TITLE` and `squash_merge_commit_message: PR_BODY`, squash only. The title is then the linted title. The body is the only source of footers. So a stray `BREAKING CHANGE:` line in a branch commit cannot change a version.
- **Release workflow.**
  - `release.yml` runs on each push to `main`, with `permissions: {}`. One concurrency group does not cancel a running release. Four jobs run, and each uses the `release` environment where it needs the App token.
  - `Draft Release` mints an App token (`actions/create-github-app-token` v3.3.0, commit `64ab729a6294000f5aa4a4bc0b73d1f32bc45510`). It runs the action with `skip-github-pull-request: true`. For a merged release pull request, this creates the draft release and changes the label to `autorelease: tagged`. It outputs `release_created`, `tag_name`, `version` and `sha`.
  - `Publish Images` runs only when the workflow created a release. It calls `image-publish.yml` with the merge commit.
  - `Publish GitHub Release` builds the wheel and the sdist and writes `SHA256SUMS.txt`. It runs `softprops/action-gh-release` (commit `efb35369e0ad2afab669f228072c1b0d510eae64`, already in use). It passes the App token, `draft: false`, `target_commitish` set to the merge commit, `overwrite_files: false` and `fail_on_unmatched_files: true`. Publishing the draft creates the tag.
  - `Release Pull Request` runs last, when the workflow created no release or the publish succeeded. It runs the action with `skip-github-release: true`, which opens or updates the release pull request.
  - `actionlint` 1.7.12 reports nothing on the file. `zizmor` reports one informational finding that the current file also has.
  - The configuration is `release-please-config.json`. It sets `include-v-in-tag`, `bump-minor-pre-major`, `always-update` and `draft`. Its `changelog-sections` map `feat`, `fix`, `perf`, `refactor` and `revert` to sections and hide the other six types. It has one package `.` of type `python`, with `uv.lock` as a TOML extra file.
  - `.release-please-manifest.json` holds the last version. The step 6 pull request writes it from `uv version --short` on `main` after the old pipeline ends.
- **Release pull request.**
  - Four files change. The App token makes the pull request trigger `ci.yml`, so the same required checks run on it. `always-update` rebuilds it from current `main` on each run, so the strict policy does not leave a quiet pull request behind.
  - `devops ci` gains `uv build` beside `uv lock --check`. The build fails if the JSONPath of `uv.lock` stops matching.
  - `devops pr check-readiness` does not run on the release pull request, and nobody writes an exemption for it. Its required checks are its gate. `changed-tests` and `fail-to-pass` find nothing to do on it, because it changes no test file and is not a defect pull request.
- **Images.**
  - Two reusable workflows exist, because a called workflow can only reduce the permissions that its caller grants. `image.yml` builds, smoke-tests and scans the service image with `contents: read` and nothing else. CI calls it when a pull request changes how the image is built or what it installs (`dorny/paths-filter`, commit `ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d`).
  - `image-publish.yml` first calls the verify job of `image.yml`. Then it pushes by digest, attests, and tags with `docker buildx imagetools create`. Only the release calls it. It also holds the release jobs of the devcontainer image, which move from `release.yml` as they are.
  - The probes of the service image smoke test (read-only, tmpfs, dropped capabilities, health) move unchanged from the two workflows that hold them today. Labels come from `docker/metadata-action`.
  - The devcontainer image already builds through two composite actions, `.github/actions/devcontainer-image` and `.github/actions/devcontainer-smoke` (#1895). `ci.yml` and `release.yml` both call them. A pull request pushes that image only to a registry on the runner and publishes nothing. So `cleanup-devcontainer.yml` prunes tags that nothing pushes any more, and it goes.
  - This decision deletes `devops devcontainer validate --oci-labels`. It compares a label literal in the workflow with a constant for the canonical repository. So it fails when a copy of the repository changes the label and not the constant.
- **Order of writes in one release.**
  - The merge of the release pull request writes nothing public. `Draft Release` creates a draft release, which has no tag. The workflow builds, scans, attests and pushes the images. From then on Image Updater can roll the digest of `service:latest`.
  - The workflow uploads the assets and publishes the draft. This creates the tag `v<version>` at the merge commit, with the App token. Argo CD resolves the constraint to the new tag only after that. So no manifest revision can reference an unpublished image.
  - For some minutes between the image and the tag, the new image runs under the old manifests. The image and the manifests follow two independent pins, and a rollback is two actions.
- **Tags are production.** A tag that matches the Argo CD constraint deploys. So a tag ruleset on `refs/tags/v*` restricts creation, update and deletion to the release App, which holds the bypass. The ruleset documentation of GitHub lists GitHub Apps among bypass actors. It says that when creations are restricted, only actors with bypass can create tags that match the pattern. Nobody verified that a user-owned repository accepts an App as a bypass actor. In an emergency only the repository owner, who administers the ruleset, can disable it.
- **Deploy.**
  - `targetRevision: ">=0.2.0"` goes on the 28 git sources in 27 files under `k8s/argocd`. Chart-version sources keep theirs. The floor is only a lower bound. It marks no change in the manifests: `v0.1.8` and `v0.2.0` hold 3 files under `k8s/argocd`, and `v0.2.27` holds 26. Argo CD takes the highest tag in range, so the floor never selects a tag. There is no upper bound, so `0.3.0` and `1.0.0` resolve.
  - Argo CD resolves the highest semver tag and skips tags that are not semver, such as the three `backup/*` tags. The other 44 existing tags are `vN.N.N`.
  - `argocd_overrides.render_at_revision` reads the resolved revision from the Application when `targetRevision` is a constraint.
- **Settings.** The `main` ruleset requires `Static Analysis`, `Tests & Coverage` and `Semantic PR title` with the strict policy that it already has. The `release` ruleset and the remaining `release/*` branches go. A person adds a tag ruleset. Merge settings are as above. A person makes these changes.
- **Hotfix and late critical fix.**
  - A fix is a fix. It merges into `main` like any item, and then the release pull request merges. The release ships whatever else is unreleased.
  - A patch-only release from a tag, with unreleased features on `main`, needs a maintenance branch and a second release-please trigger with `target-branch`. Nobody built them, because nothing needed them. Feature flags are another answer.
- **Failure and recovery.**
  - If the image or publish job fails for a temporary reason, a draft and no tag remain. "Re-run failed jobs" finishes the work. The publish step finds the draft by its tag, and then the last job runs.
  - If a failure on the merge commit repeats, delete the draft and merge the undo pull request and the fix. The failed version is never published.
  - A merged release pull request that still has `autorelease: pending` stops new release pull requests until someone re-runs the workflow.
  - A push to `main` while a draft is unpublished waits in the concurrency group. GitHub keeps one waiting run per group and cancels an older waiting run. That is safe, because the newer run finds the merged release pull request and does the same work. Nobody verified this. Premise 10 of the rehearsal tests it.
  - After a failed publish, the image tag `service:latest` already points to the image of the unpublished release. The undo pull request does not move it back. The next release moves it. A person can point it at the old digest with `docker buildx imagetools create`.
  - Until the draft is published or undone, a push to `main` opens a wrong release pull request. On the clone it listed 80 entries. Do not merge it. The undo pull request makes the next proposal correct again.
- **Planner.**
  - The roadmap Service stays suspended. Its code stops reading a version. A milestone is its number, a title, a due date and a state. One key orders milestones: the due date, then the number. Where milestones are listed, the code applies it once.
  - The planner creates the next bucket with a due date `bucket_days` after the last one (a new setting, default 7). It titles the bucket with that ISO date. A person can rename it to a theme at any time, because identity is the number.
  - A bucket is planned, then started, then delivered when every issue in it is closed. The planner closes a delivered bucket as its last write.
  - This decision deletes `CUT`, `MERGED` and `SHIPPED`, the release-branch writes and the closing-keyword parser. GitHub's `closingIssuesReferences` supplies which pull request closes which issue. Priorities, caps, slots and critical-fix placement do not change. The planner renames the `release_*` settings to `milestone_*`.
- **OpenSpec.** The pull request that closes the issue archives its change as its last commit, after the final rebase. It runs `devops openspec archive <name>`, which runs the pinned tool under the isolated config and then `validate --all --strict`. Readiness checks that the diff holds the archived folder and no active one. A change folder lives for one issue and one pull request.

## Versioning and Milestones

The tool derives the version. Nobody chooses it. `bump-minor-pre-major` is the one pre-1.0 setting. It keeps a breaking change from reaching `1.0.0` by accident.

`bump-patch-for-minor-pre-major` makes a `feat` a patch before `1.0.0` and reserves the minor for a breaking change. This decision does not set it, because the owner's correction is that a `feat` can make the next release `0.3.0`. The consequence is a faster minor.

All 53 released sections of `CHANGELOG.md` have an Added category. So with this setting nearly every release raises the minor. The 15 releases of 2026-10-01 to 2026-10-21 become `0.3.0` to `0.17.0`. This is an estimate from the Added categories, not from commit types. 8 of the 40 latest squash titles at `3ef69850` are `feat`. Setting the other flag takes one line, and a later decision can do it.

`1.0.0` happens when the owner merges a pull request titled `chore: release 1.0.0`. Its body has the paragraph `Release-As: 1.0.0`. release-please then opens `chore(main): release 1.0.0`, and the owner merges that. The tool does not check `Release-As`, and it accepts a version lower than the current one. So the owner reads the number in the title of the release pull request before the merge. From `1.0.0` the pre-major setting has no effect and [AGENTS.md](../../AGENTS.md) governs.

Nothing assumes `0.2.N`. Tags are `v` plus the version (`include-v-in-tag`, no component in the tag). The 44 existing tags and the Argo CD floor keep working. The manifest holds the last version of the old pipeline. release-please finds the release `v<that version>` and takes the commits after it. It needs no bootstrap commit.

The first release of the tool is whatever it derives from the commits after that tag. The deletion pull request has `!` in its title and a `BREAKING CHANGE:` paragraph, because `devops release` and `devops roadmap close` disappear. So the first release should be `0.3.0`, if the owner holds it as step 14 says. Without that hold, the first release can be a patch, when every merged pull request is a fix or a refactor.

A milestone no longer predicts a release. The jobs key on the number of the milestone, which survives a rename. They use one order: the due date, then the number, with a milestone that has no due date last. The first open milestone in that order is the current one. The four open milestones have no due date, so the rename step gives them one.

There is no release gate and no scope rule. An item of a later bucket that merges early ships in the next release and closes correctly. Readiness no longer judges which bucket an item belongs to. The release path never reads a milestone.

## Conventions That Change

Each line is a convention of this repository, not of a tool. This decision drops or rewrites each one.

- **Release branches and the cut** go. Topic pull requests target `main`, and `main` is the only long-lived branch. The hook `no-commit-to-branch` lists `main` only. This decision deletes the `release` ruleset.
- **The release pull request made by hand or by the Service** becomes the one that the tool opens. It was `feat(release): vX.Y.Z`, with 188 to 990 files. It has four files and comes from `release-please--branches--main`.
- **The version as the milestone title**, and "the next patch", go. The version comes from the titles on `main`.
- **Changelog fragments**, the collector and the Keep a Changelog sections as the writing rule go. The title is the entry. `CHANGELOG.md` keeps its 53 hand-written sections as history. The preamble sentence that names Keep a Changelog and the `## [Unreleased]` heading go.
- **Free-form pull request titles** become Conventional Commits, and a check enforces them. 880 of 882 merged titles conform already.
- **Squash settings** `COMMIT_OR_PR_TITLE` and `COMMIT_MESSAGES`, with merge commits and rebase merges allowed, become `PR_TITLE` and `PR_BODY`, squash only.
- **The pull request template** loses Type of Change, Base Branch, Item, Task file and Changelog fragment. It keeps a summary and `Closes #<issue>`.
- **`Part of #N` and the closer** go. `Closes #N` is live on `main`. An item is one issue and one pull request. There is no closure comment with check verdicts. The required checks and the pull request body are the verdict.
- **A milestone is a release** becomes: a milestone is a planning bucket. There is no release gate, no scope rule, no rule that a hotfix needs an empty milestone, and no milestone close by the release workflow.
- **The tag at merge, before the images,** becomes the tag as the last write.
- **Argo CD tracks `main`** becomes: Argo CD tracks the highest tag at or above `0.2.0`.
- **Copilot reviews pull requests into `main` automatically, which meant the release pull request alone,** becomes: Copilot reviews a pull request when a person requests it. An automatic pass on every pull request into `main` would review all of them and spend the monthly token budget. The newest pull request with a Copilot review is #1283 (v0.2.28, 2026-10-07), and the release pull requests #1615 and #1720 have none. So the automatic pass may be off already. Nobody verified where it is configured. Neither ruleset has a rule for it.
- **The OpenSpec archive at the cut** becomes the archive in the closing pull request.
- **`docs/RELEASE_NOTES.md`, the compactor and the Historical Documentation Compaction bullet** go. GitHub Releases and `CHANGELOG.md` hold the notes.
- **`docs/ROADMAP.md` written at the cut** becomes rendered from GitHub by the render job or command. No release writes it. Nobody writes it by hand.
- **Two readiness rules about the release files** go. One rule says that an item pull request edits neither `CHANGELOG.md` nor the version. The other is a file allowlist for the release pull request.
  - AGENTS.md says: "Never edit `CHANGELOG.md` or `docs/ROADMAP.md` in topic PRs." Step 6 rewrites that sentence, so only the release pull request edits `CHANGELOG.md`.
  - release-please reads the file from `main`, so it keeps a stray edit in its output. The edit shows in the diff of its own pull request.
  - A guard for it would be custom code for a rare event, so none stays.
- **Triggers keyed on a branch name** go. Each condition keys on the event and the changed paths. One test per gate shows that the gate runs for a pull request into `main`.
- **The image build exists twice** and becomes `image.yml` and `image-publish.yml`.
- **Stale version literals** that no bump touches become `get_version()` or a placeholder. They are `http/broker.py:41`, `docs/github-pages.config.yaml:23`, `docs/_layouts/default.html:32` and four lines in `docs/DEVCONTAINER_USAGE.md`. `pyproject.toml` is the one literal.
- **A convention is a reason to keep custom code** becomes: it never is. [#1874](https://github.com/dan-petty/devops-cli/issues/1874) put that sentence in AGENTS.md.

## Cutover and Sequence

The old pipeline publishes v0.2.39 from `release/v0.2.39`. Its end is the moment when all of these are true:

- The `release.yml` run is green.
- The GitHub Release and both attested images exist.
- Tag `v0.2.39` is on the squash commit on `main`.
- Milestone v0.2.39 is closed.
- `uv version --short` on `main` reads `0.2.39`.

This decision is a record. It merges before that moment, under the old rules. It brings the last changelog fragment and task file that those rules need. Nothing else of this sequence merges before the end of the old pipeline. The OpenSpec items that already target `release/v0.2.39` are not part of this sequence. Only work that is inert may start earlier: the App, the environment and the rehearsal.

After that moment the following stop, and nobody runs them again:

- the cut;
- the `release/vX.Y.Z` branches (nobody opens `release/v0.2.40`);
- the `chore/cut-*` and `chore/open-*` pull requests;
- `devops release` and `devops roadmap close`;
- fragments and `Part of`.

Every topic pull request targets `main`.

Each step is one item. The item states its written cost before work starts (see What Stays Custom). A person files it with `devops roadmap intake` after this decision merges, or someone rewrites an existing item. One pull request delivers it and keeps `devops ci` passing. Only a person can do the steps marked person-run. No pull request carries both systems, so at no point can both make a release.

1. `docs(adr)`: this decision, which supersedes ADR 0011, into `release/v0.2.39`.
2. `chore(settings)`, person-run and inert, before the end of the old pipeline. Install the release App on this repository only. Create the `release` environment for `main` with `RELEASE_APP_CLIENT_ID` and `RELEASE_APP_PRIVATE_KEY`. Run the rehearsal in a throwaway copy of the repository (below).
3. `chore(settings)`, person-run, right after the old pipeline ends and not before: the squash settings.
4. `feat(k8s)`: Argo CD follows release tags ([#1862](https://github.com/dan-petty/devops-cli/issues/1862)).
   - This comes first. Once pull requests land on `main`, applications that still track `main` deploy manifests ahead of any published image.
   - The parent applications `bootstrap` and `cluster` read their own definitions from the revision they track. A person sets them to sync policy none before this merges. They flip to the constraint after `argocd app diff` is empty. That can happen only after a release publishes a tag that contains the constraint.
   - Until then the child applications keep tracking `main`. So no pull request that changes a manifest under `k8s/` merges in that window.
   - Or a person sets each application by hand, after `argocd app diff`: `argocd app set <app> --revision ">=0.2.0"`. That resolves to the last release of the old pipeline, whose content equals `main`.
5. `ci(image)`: the read-only reusable workflow `image.yml` builds, smoke-tests and scans the service image. The pull request build then holds no write scope ([#1858](https://github.com/dan-petty/devops-cli/issues/1858)). The pull request build of the devcontainer image holds none already (#1895). This step deletes `cleanup-devcontainer.yml`.
6. `feat(release)`: release-please opens the release pull request, topic pull requests target `main`, and merging the release pull request publishes ([#1861](https://github.com/dan-petty/devops-cli/issues/1861)).
   - It adds the configuration, `release.yml`, `image-publish.yml` and `pr-title.yml`. It adds `uv build` in `devops ci`, trunk-shaped readiness, main-only triggers and hook, and the Renovate rule. It also changes `AGENTS.md`, `CONTRIBUTING.md`, `RELEASE_CYCLE.md`, the template and the `CHANGELOG.md` preamble.
   - From its merge, a push to `main` opens the first release pull request and publishes nothing.
7. `chore(settings)`, person-run, after step 6: the required checks and the tag ruleset. Set the checks after `Semantic PR title` reports on a pull request ([#1752](https://github.com/dan-petty/devops-cli/issues/1752) decides the first two). The tag ruleset waits for step 6, so it never blocks the old path before the new path exists.
8. `ci(k8s)`: the Argo CD build gate runs in `devops ci` on every change to `k8s` ([#1860](https://github.com/dan-petty/devops-cli/issues/1860)). The cut was the only caller of the gate.
9. `docs(workflow)`: the rest of the instructions. They include SDLC, ROUTINE_TASKS, CONTEXT, the knowledge base and the instruction generator with its prompt. The step also covers the issue templates, small strings and stale version literals.
10. `refactor(release)!`: delete the bespoke release machinery ([#1863](https://github.com/dan-petty/devops-cli/issues/1863)). Its body carries `BREAKING CHANGE:`, which makes the first release a minor.
11. `chore(docs)`: remove `docs/RELEASE_NOTES.md` and `devops docs compact` ([#881](https://github.com/dan-petty/devops-cli/issues/881)).
12. `refactor(roadmap)` and `refactor(github)`, after step 6, in any order except where one needs another.
    - A milestone is identified by number and ordered by due date, never a version.
    - Then the planner creates date-titled buckets and closes a delivered bucket.
    - GitHub's closing references replace the keyword parser. The one-time ADR 0001 migration goes. The Copilot pass commands go.
    - Last, `Release` becomes `Milestone` in the planner, its settings and the board.
13. `chore(settings)`, person-run.
    - After step 10, delete the `release` ruleset and the remote `release/v0.2.*` and `chore/open-*` branches.
    - After step 12, rename the milestones and give them due dates.
    - After the first release, flip `bootstrap` and `cluster` to the constraint.
14. `chore(release)`: the first release made by release-please is published, and its cost is measured ([#1865](https://github.com/dan-petty/devops-cli/issues/1865)). The owner holds the first release pull request until step 10 merges. This is a choice, not a coupling. It means the first release is built on a tree without the old system.

The order follows dependencies. Step 4 comes before step 6 for the reason given. Step 8 comes before step 10, because the cut was the only caller of the gate. Step 9 comes before step 10, because `devops docs check` fails on a document that names a missing command. So no document may name `devops release` or `devops roadmap close` when they go.

After the old pipeline ends, the old `release.yml` runs red on the pushes of steps 4 and 5. Its tag guard refuses a push to `main` that is not a release. Nobody fixes it, because step 6 replaces it.

From the end of the old pipeline to the first release at step 14, no release publishes. A critical fix merges to `main` like any change and ships in that first release. If it cannot wait, the owner publishes the first release without the hold for step 10 (step 14).

Step 6 merges only after a rehearsal in a throwaway copy of the repository. The rehearsal checks the premises that no document settles. Each premise names what happens if it fails.

1. A draft release that release-please creates receives its assets through `softprops/action-gh-release` with the App token. Publishing the draft then creates the tag at the merge commit. A tag ruleset names the App as bypass actor on a user-owned repository. Nothing in the repository depends on annotated tags: 43 of the 44 existing tags are annotated, and `v0.2.21` is lightweight.
   - If it fails, use the first fallback. If only the bypass actor fails, use Decision 9.
2. A pull request that the App token opens triggers `ci.yml` and satisfies the required checks under the strict policy.
   - If it fails, step 6 waits until the design changes. No fallback exists.
3. A squash with `PR_TITLE` and `PR_BODY` carries `Release-As`, `BREAKING CHANGE:` and `Closes #N` into the release pull request.
   - If it fails, step 6 waits until the design changes. No fallback exists.
4. A `ci:` pull request that merges while the release pull request is open leaves it current.
   - If it fails, step 6 waits until the design changes. No fallback exists.
5. The `uv.lock` JSONPath, `uv lock --check`, `uv build` and the Docker `uv sync --locked` pass on a real release pull request. The bundled 17.6.0 builds that pull request.
   - If it fails, use the second fallback.
6. `amannn/action-semantic-pull-request` accepts a title with `!`.
   - If it fails, step 6 waits until the design changes. No fallback exists.
7. Merging a release pull request whose notes say `closes [#N](url)` does not close an issue that a person reopened.
   - If it fails, use the second fallback.
8. The second call of the action opens nothing after the tag exists. The undo recovery restores a proposal.
   - If it fails, use the first fallback.
9. The labels `autorelease: pending` and `autorelease: tagged` exist, or the tool creates them.
   - If it fails, a person creates the two labels.
10. GitHub keeps one waiting run per concurrency group. The newer waiting run finds a merged release pull request and does the work of a cancelled run.
    - If it fails, step 6 waits until the design changes. No fallback exists.

The fallbacks are:

- First fallback: let release-please tag at merge, and move `service:latest` as the very last step. Then the manifests run for a few minutes ahead of the image.
- Second fallback: run the release-please CLI from a hash-pinned `package-lock.json`, as OpenSpec does, for the newer library.
- Third fallback: use the two-phase flow of python-semantic-release. Use it when release-please stalls, or when the second fallback fails.

## What Stays Custom

Each piece below names the open tool that we considered and why it does not cover the capability. This decision adds about 450 lines. They are 36 of configuration, 124 of `release.yml`, 19 of `pr-title.yml` and about 40 of readiness. They also include about 30 for `uv build`, about 150 net in the planner, and about 50 of archive wrapper and miscellany.

About 310 lines move into `image-publish.yml`. About 14,400 lines go. This ADR gives size in lines only, because no file in this repository records tokens. AGENTS.md (Open Tools Before Internal Code) requires a written cost for each build: tokens to implement, maintain and fix, and elapsed time. The item of each step states that cost before work starts. Until it does, a build in this list is a proposal.

- **Pull request readiness** (`commands/pr.py`, about 540 lines of release-process and grounding rules, which shrink to about 240).
  - Considered: required status checks and rulesets, `amannn/action-semantic-pull-request`, the pull request template, and GitHub's `PullRequest.closingIssuesReferences`. This decision adopts the title action for the title, in place of any title rule of our own. It adopts the GitHub field for the closing half, in place of the regular expression.
  - It keeps what no generic check knows. The issue is open and on the roadmap board, and the pull request carries the archived change folder of that issue. It also checks that the base is the default branch, that the checks pass and that review threads are resolved.
  - This decision deletes branches, cuts, fragments, version files, release scope and `Part of` from it. It also deletes any exemption for the release pull request: a check that does not apply is not run there.
- **Item admission, caps, slots and critical-fix placement** (`roadmap/reprioritize.py` 3,316 lines, `store.py`, `github_store.py`). Considered: GitHub milestones and Projects as storage only. release-please, towncrier, git-cliff and python-semantic-release do not plan scope. The engine is project policy (a cap, slots, P0 and P1 placement). It loses every version and every release-branch notion. It keeps planning.
- **The Argo CD build gate and host overrides** (`k8s/argocd_gate.py` 316 lines, `argocd_overrides.py` 173).
  - Considered: `kustomize build` with kubeconform, `argocd app diff --local`, and conftest. A 20-line Rego rule enforced the placeholder-domain rule in scratch.
  - The rule is policy of this repository. `deploy-stack` shares `argocd_overrides._host_fields`, so a Rego copy duplicates it. The cut was the only caller of the gate, so the gate moves into `devops ci` and runs on every change to `k8s/**`.
- **The service image smoke test** (YAML in `image.yml`). Considered: `container-structure-test`, which was not run. The probes are specific to this repository and move unchanged.
- **The OpenSpec archive wrapper** (`devops openspec archive`, about 20 lines, in the module of ADR 0010). Considered: to run `openspec archive` directly, which ADR 0010 forbids, because the per-user configuration and the telemetry of the tool must stay isolated. The wrapper runs the pinned tool and then validates.
- **Release glue in YAML.**
  - It is `release.yml` (124 lines), `image-publish.yml` (moved from `release.yml`, about 310 lines) and `pr-title.yml` (19 lines).
  - Considered: release-please-action, create-github-app-token, softprops/action-gh-release, amannn/action-semantic-pull-request and docker/metadata-action. This decision adopts all of them. Only the wiring is ours.
  - The release path has no Python, no version logic, no changelog code and no cut. It has no prepare workflow, no release gate and no milestone read.

## Considered Options

- **A. Trunk with release-please, run as the pinned action (chosen).**
  - It is the only candidate that derives versions and lands a release through a reviewable pull request. ADR 0011 rejected it for now, mainly because of a second writer on its force-pushed branch (the `towncrier` output, an OpenSpec archive). It also named notes from commit titles, the undocumented TOML parser, the tag at merge before the images exist and the App token. With fragments and the release-time archive withdrawn, it is the only writer of four files. The other reasons are risks, which this ADR lists below.
  - The notes are the pull request titles (median 82 characters against 270 as fragments). So detail moves to pull request bodies, the OpenSpec change and generated documents.
  - The last release of release-please is from 2026-08-24. Its action lags the library by five minor releases. So the pinned action writes `closes` where upstream writes `refs`.
  - The `uv.lock` JSONPath relies on an undocumented tagged-value TOML parser ([release-please #2455](https://github.com/googleapis/release-please/issues/2455), open). `uv lock --check` on the release pull request guards it.
  - Draft-then-publish, the App token that starts CI, and the App as a tag-ruleset bypass actor did not run here. They are premises of the rehearsal.
- **B. Trunk with python-semantic-release 10.7.0 (the other formal tool; the verified fallback; not adopted).**
  - It derives the same versions. It has no pull request mode, so a protected `main` needs an administrator token, which the rule against pushes to `main` forbids.
  - We must write the glue that opens and updates the pull request, which release-please gives for free.
  - A shallow or tagless checkout prints `0.1.0` and does not fail. Its GitHub Action is an unpinned Docker image. It has one main maintainer. It stays the fallback if release-please stalls.
- **C. Trunk with `towncrier`, `uv version`, a prepare workflow and a publish workflow (ADR 0011; superseded).**
  - It deleted the cut and kept the conventions of this repository as reasons for custom code. It kept typed fragments, with `towncrier` 26.9.0 and a `release` dependency group. It kept a `workflow_dispatch` prepare workflow that opens `chore/release-vX.Y.Z`. A release gate first checks that the milestone is empty. The gate also checks that every fragment names an issue of the milestone.
  - It kept the milestone title as the version passed to `uv version`. It kept a trunk scope rule that lets only the items of the lowest milestone merge. It also kept a size test, `Part of #N`, the closer and the compactor.
  - Its own estimate was about 55 lines of Python, about 40 of shell and about 470 of workflow. It also needed a `uv` pin parity test, a `Release Gate` check and a hold on the first release.
  - The owner withdrew it. Each of those pieces protects a convention that the owner does not hold. An open tool does the whole job: the tool derives the version, the title is the entry, and the tool opens the pull request.
- **D. Keep the integration branch and replace the cut with open tools** (`towncrier`, `uv` and a pull request that a workflow opens into `release/vX.Y.Z`): rejected. It removes the cut, the collector and the compactor (about 1,500 lines). It leaves `close.py` and its call sites, sync pull requests, release pull requests of hundreds of files, an untested release tip and two rulesets. These are clusters 1, 5 and 8.
- **E. Trunk, release by pushing a tag, versions and notes from commits** (git-cliff, commitizen, hatch-vcs): rejected.
  - A person who pushes a tag publishes with no pull request, no checks before the publish and no test of the tip.
  - `hatch-vcs` had its last release in 2025-05. It needs `SETUPTOOLS_SCM_PRETEND_VERSION` in image builds without `.git`.
  - The notes that GitHub generates list pull requests by label, and CI does not enforce the label audit. `changie` has the shape of `towncrier` in Go and keeps the fragment rule of Option C.
- **F. Others, not run.** The JavaScript `semantic-release`, and release-please as a CLI from a hash-pinned `package-lock.json`. The CLI is the named fallback for the lag of the action. It costs the outputs that the action gives.

## Consequences

- About 6,730 lines of source go.
  - Whole files, 5,737 lines, in the release code: `release/cut.py` 1,126, `release/changelog_fragments.py` 286, `release/notes_compaction.py` 109, `release/__init__.py` 1, `commands/release.py` 888, `github/release_notes.py` 111 and `models/release.py` 51. Whole files in the roadmap and cluster code: `roadmap/close.py` 618, `k8s/argocd_live_report.py` 312, `roadmap/migrate.py` 730 and `roadmap/document.py` 244. Whole files in the documents and review code: `docs/compactor.py` 547, `github/copilot_budget.py` 216, `github/review_thread_issues.py` 377 and `github/issue_closure.py` 121.
  - Pieces, about 990: 83 in `roadmap/request_plan.py`, 61 in `roadmap/run.py`, 72 in `commands/roadmap.py` and about 300 in `commands/pr.py`. Six `Release*Error` classes in `exceptions/git.py` take 137. The rest is the `Part of` machinery (about 60) and the release, process-kind and fragment constants (about 120). It also holds the `--oci-labels` validator (about 60) and the release and close strings (about 100).
- About 6,625 lines of tests go as whole files.
  - They are `test_release.py` 2,975, `test_roadmap_close.py` 876, `test_release_changelog_fragments.py` 283, `test_release_notes_sync.py` 192, `test_release_notes_compaction.py` 120 and `test_k8s_argocd_live_report.py` 356. Also `tests/support/release_notes_examples.py` 44, `test_docs_compactor.py` 514, `test_github_copilot_budget.py` 449, `test_gh_issue_closure.py` 220, `test_roadmap_migrate.py` 509 and `test_roadmap_document.py` 87.
  - Other test files lose cases, among them `test_pr_cmd.py` (2,993 lines), `test_roadmap_reprioritize.py` (3,572), `test_roadmap_lifecycle_properties.py` (3,471) and `test_github_pr_threads.py` (1,322).
  - We rewrite the tests that assert the old job layout of `ci.yml` and `release.yml` against the new workflows. One test per gate shows that it runs for a pull request into `main`.
- About 674 lines of workflow go: `release.yml` 467, the `ci.yml` service-image job 94 and `cleanup-devcontainer.yml` 113. About 180 arrive new (`release.yml`, `pr-title.yml` and the configuration). About 310 move into `image-publish.yml`.
- These parts are removed:
  - the `devops release` and `devops roadmap close` commands, `devops pr copilot-pass` and `devops pr threads file-issues`;
  - the `resource://release/status` MCP resource;
  - `docs/RELEASE_NOTES.md` (36 lines), `docs/commands/release.md` (188 lines) and the `changelog.d` directory.
- `RELEASE_CYCLE.md` falls from 264 lines to about 90. A `git grep` for `changelog.d`, `release/v`, `release/**`, `devops release`, `roadmap close`, `chore/cut` or `chore/open` finds 53 files at `3ef69850`. The count leaves out `tests/`, `docs/adr/`, `docs/agent/`, `CHANGELOG.md`, `changelog.d/`, `docs/RELEASE_NOTES.md` and the generated `tools.lock`. Among the 53 are `AGENTS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `CONTEXT.md`, eleven knowledge base articles, the instruction generator and `lang/en`. The same pattern finds 43 test files. `AGENTS.md` ends smaller.
- In all, about 14,400 lines go: 6,730 of source, 6,625 of tests, 674 of workflow and 413 of documents. About 450 arrive and about 310 move. ADR 0011 counted about 9,900 deleted against 565 added.
- The release notes are the pull request titles. The median is 82 characters, against 270 as fragments. Detail that a fragment carried belongs in the pull request body, the OpenSpec change and the generated documents. A title that is not conventional, or that someone edits in the merge dialog, drops out of the notes without a warning.
- Releases follow the commits, not a plan. A `feat` raises the minor before `1.0.0`, so the minor moves often. A patch-only release is not possible while unreleased features sit on `main`.
- A `fix` or `feat` ships only when a person merges the release pull request. That merge is the only gate. A `chore(deps)` update to the base image or to a runtime dependency releases nothing alone. So those updates carry the title `fix(deps)`: Renovate does it for the service `Dockerfile`, and the author does it otherwise. A security fix in the image that has the title `chore` waits for the next release.
- The strict required-checks policy now binds every pull request, not only the release pull request.
  - Each merge into `main` makes every other open pull request update its branch and run its checks again. A user-owned repository has no merge queue.
  - 39 pull requests squashed into release branches on 2026-10-21 alone (UTC). So the cost is real, and it falls on the oldest-first order of merging.
  - The decision keeps the policy, because the merged tree is then the tested tree. `always-update` also re-runs the checks of the release pull request on every push to `main`. `ci.yml` cancels a run that a newer push supersedes.
- GitHub Pages publishes `docs/` from `main`, so unreleased documentation goes live when it merges. A broken site build now breaks Pages at the merge. [#1651](https://github.com/dan-petty/devops-cli/issues/1651) gets a rewrite: it builds the site on pull requests that change `docs/`.
- The closure comment with check verdicts and acceptance criteria that `roadmap close` posted is gone. The required checks and `devops pr check-readiness` verify both before the merge.
- A person can reopen an issue after its pull request merges. The merge of the release pull request may close it again, until the action bundles release-please 17.10.4 or later. 127 open issues have a `changelog.d` criterion. Those criteria are void. A person removes them when they edit those issues.
- The last release pull request that Copilot reviewed is #1283 (v0.2.28). The automatic review may be off already. The release pull request is now a generated diff of four files. Copilot reviews a pull request only when a person requests it, so no automatic review gate remains.
- The image and the manifests follow independent pins. When the tag ruleset exists, only the release App can create a tag. A rollback is two actions.
- `docs/ROADMAP.md` is no longer rewritten at a release. It lags GitHub until a person or the render job renders it.
- This decision supersedes ADR 0011 and amends three other ADRs.
  - ADR 0011 gets one first line that names this ADR. Nothing else in it changes.
  - ADR 0001: milestones are planning buckets, not releases, and `docs/ROADMAP.md` is rendered. It gets a dated note that points here.
  - ADR 0004: [#1752](https://github.com/dan-petty/devops-cli/issues/1752) records the amendment (required checks, no merge queue, what runs locally). This decision adds `Semantic PR title` to its list.
  - ADR 0010: the archive moves from the cut to the closing pull request. That makes the cut-time archive code unnecessary: the archive-ordering function and the rehearsal of the cut. They merged in #1868. [#1846](https://github.com/dan-petty/devops-cli/issues/1846) edits ADR 0010 in place and deletes the code that exists only for the cut. The overlap check does not exist only for the cut, so it stays.
    - Corrected on 2026-10-22: the overlap check stays (evidence in docs/agent/tasks/task-1846-the-openspec-gate-drops-the-cut-only-code.md).
- Nothing in the release path waits for the roadmap Service ([#1562](https://github.com/dan-petty/devops-cli/issues/1562)). The planner changes can merge on any date after step 6.

## Decisions Taken

Each point below needed the owner. This ADR decides each one. Merging this ADR confirms it. A later ADR can reverse it.

1. **The tool is release-please, run as the pinned action.** It owns versions, the changelog, the release pull request and the release record. The fallback is python-semantic-release.
2. **Before `1.0.0`, only `bump-minor-pre-major` is set.** A `feat` raises the minor. `bump-patch-for-minor-pre-major` is a one-line change if the cadence becomes unwanted.
3. **`1.0.0` is a `Release-As` paragraph that the owner merges.**
4. **The pull request title is the changelog entry.** The detail lives in the body, the change folder and the generated documents.
5. **One issue is one pull request.** This ADR retires `Part of #N`. An issue too large for one pull request becomes sub-issues, which spend filing quota under #1153.
6. **Milestones are planning buckets.** A due date names a bucket by default, and a person can rename it to a theme. The due date orders it. A bucket closes when every issue in it is closed. The release never reads one.
7. **A person decides when to release.** There is no schedule. Nobody merges the release pull request automatically.
8. **One release App serves this repository only.** It holds contents, pull requests and issues write. Its credentials live in the `release` environment as `RELEASE_APP_CLIENT_ID` and `RELEASE_APP_PRIVATE_KEY`. It is separate from the identity of the roadmap Service (ADR 0002, #1562, #1647), so the release path waits for neither.
9. **A tag ruleset on `refs/tags/v*` protects tags.** A person creates it at step 7. It restricts creation, update and deletion, with the App as bypass actor. If this user-owned repository does not accept an App as a bypass actor, the ruleset restricts only update and deletion. The setting item then records that any writer with contents access can create a tag that the cluster follows. A later ADR revisits this.
10. **The `main` ruleset requires `Static Analysis`, `Tests & Coverage` and `Semantic PR title`**, with the strict policy kept. The `release` ruleset and the `release/v0.2.*` branches go after step 10. The decision does not rely on a merge queue.
11. **Immutable releases stay off.** The setting exists and answers `enabled: false`. Nobody verified that the publish order (assets uploaded, then published) works with it. A person tests that before turning it on.
12. **GitHub Pages keeps its legacy build of `main:/docs`** until the item that builds the reference pages at publish adds a Pages workflow. A site build on pull requests that change `docs/` guards the merge.
13. **`docs/RELEASE_NOTES.md` and `devops docs compact` go** ([#881](https://github.com/dan-petty/devops-cli/issues/881)). The render command writes `docs/ROADMAP.md` from GitHub, and no release writes it. A later decision can stop committing it.
14. **Copilot review is by request.** No pull request gets an automatic pass by policy. A person requests one. The Copilot pass and thread-filing commands go. This holds if the automatic pass is off already.
15. **The archive happens in the closing pull request** ([#1846](https://github.com/dan-petty/devops-cli/issues/1846)).
16. **The strict required-checks policy stays for every pull request.** The cost is serialized merges.
17. **A convention is never a reason to keep custom code.**
18. **Adjacent refactors are not part of this decision.** A conftest policy for the placeholder-domain rule and `container-structure-test` for the smoke test are each their own item, if someone ever files one. No step waits for them.

- Pending a person: create the release GitHub App and install it on this repository only. Keep its private key out of the repository.
- Pending a person: set `RELEASE_APP_CLIENT_ID` and `RELEASE_APP_PRIVATE_KEY` in an environment named `release` that deploys from `main` only. Do this before the rehearsal.
- Pending a person: run the rehearsal in a throwaway copy of the repository. Record what it showed for each premise of the Cutover.
- Pending a person: right after the old pipeline ends, set the squash settings to `PR_TITLE` and `PR_BODY` with squash only.
- Pending a person: before step 4 merges, set the sync policy of the Argo CD applications `bootstrap` and `cluster` to none.
- Pending a person: set `Static Analysis`, `Tests & Coverage` and `Semantic PR title` as required checks of the `main` ruleset. Do this after `Semantic PR title` reports on a pull request. Keep the strict policy on. Find and turn off any automatic Copilot review.
- Pending a person: after step 6 merges, create the tag ruleset on `refs/tags/v*` with the App as bypass actor. Record what `devops gh api repos/dan-petty/devops-cli/rulesets` then lists.
- Pending a person: after the deletion pull request merges, delete the `release` ruleset and the remote `release/v0.2.*` and `chore/open-*` branches. Confirm that no workflow trigger names `release/**`.
- Pending a person: rename the open milestones to dates or themes. Give them due dates. Do this once the planner no longer parses a title.
- Pending a person: edit the 127 open issues whose criteria name a `changelog.d` fragment. Or accept that the criterion is void.
- Pending a person: read the version in the first release pull request and merge it. Record the wall time, the number of actions, each failed step and the size of the release pull request. Put them next to the figures of v0.2.36 and v0.2.37.
- Pending a person: when a tag with the constraint exists, flip the Argo CD applications `bootstrap` and `cluster` to `>=0.2.0`. Do this after `argocd app diff` shows no change. Confirm that every application resolves to the new tag.

## Revisit Conditions

- The rehearsal falsifies a premise. The list of premises names the fallback or the stop rule of each one.
- release-please stalls (no release for six months and an open advisory). Or the action does not bundle release-please 17.10.4 or later within a quarter, and the rehearsal shows that `closes [#N](url)` closes a reopened issue again.
- GitHub lets a user-owned repository enable a merge queue. Or immutable releases are enabled for it. Or an App cannot be a bypass actor on the tag ruleset of this repository.
- The minor moves faster than the owner wants. Then set `bump-patch-for-minor-pre-major`.
- A patch-only release is needed while unreleased features sit on `main`. Then build the maintenance branch and the second trigger, or put the features behind flags.
- The constraint of Argo CD resolves an unexpected tag, or the cluster needs a rollback faster than two actions. Then pin the application to a tag by hand and reconsider the `semver` strategy of Image Updater.
- Serialized merges under the strict policy cost more than a day of waiting in any week. Then reconsider the policy with a merge queue or a post-merge check.
- Release 1.0.0: this ADR continues under Semantic Versioning and deprecation periods. The pre-major setting stops mattering.
