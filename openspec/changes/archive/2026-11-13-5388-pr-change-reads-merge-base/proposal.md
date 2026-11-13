# Proposal: #5388

## Why

The issue #5388 reports two readers of pull request changes that do not use the merge base. The Jev completeness check of the row `stage_ready` reads the diff of the pulls endpoint (`src/devops_cli/roadmap/stage/stage_ready.py`, `_jev_holds`). The scheduled release merge reads the pulls files list (`src/devops_cli/release/merge_candidate.py`, `_changed_files`). GitHub can keep a stale `base.sha` after the merge base of a pull request moved. Then these two reads hold files of other changes: Jev judges a plan with files that the plan does not change, and the release guard refuses a release pull request for a file of `main`. The fix of #2530 moved the readiness reads to the compare of the base branch and the head commit for the same cause.

## What Changes

- `GitHubClient.get_compare_diff(repo, base, head)` reads the unified diff of `head` since its merge base with `base` from the compare endpoint, in the diff media type. It and `get_pr_diff` share one private read of a diff.
- The Jev completeness check of the row `stage_ready` reads the diff of the draft with `get_compare_diff` from the base branch of the draft (`PullStatus.base_ref`) and its head commit. It reads no diff of the pulls endpoint.
- The pick of the scheduled release merge reads the files of a release pull request with `GitHubClient.get_compare_files` from the base branch of the pull request and its head commit. It sends no pulls files request. The protocol `RestSession` of the pick names the `client` of the session.
- `RELEASE_CYCLE.md` says where the file guard reads the files.
- Item 2 of the issue, the review of a pull request that a merge commit merged, is not in this change. It moves to #5397, because the compare read of `devops review pr` is only in the open change of #5346.
- The change alters what the row and the pick read from GitHub, which a consumer observes, so it carries two spec deltas.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/ready`: the new requirement Jev reads the diff of a stage draft from the compare of its base branch. The requirement The Service asks Jev about the criteria of a green stage draft does not change.
- `release-scheduled-merge`: the new requirement The pick reads the files from the compare of the base branch. The requirement The pull request must change only the files that release-please writes does not change.

## Impact

- Code: `src/devops_cli/github/client.py`, `src/devops_cli/roadmap/stage/stage_ready.py`, `src/devops_cli/release/merge_candidate.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_ready_jev.py`, `tests/release/test_release_merge_pick.py`, `tests/github/test_github_client.py`
- Docs: `RELEASE_CYCLE.md`
- Permissions: the compare endpoint needs `contents: read`. The job of `.github/workflows/release-merge.yml` gives `GITHUB_TOKEN` `contents: read`. The Service already reads the compare endpoint with its App token in `read_draft` (`src/devops_cli/roadmap/implement/implement_pull.py:296`).

## Feasibility

- `src/devops_cli/roadmap/stage/stage_ready.py:114` on `origin/main` (4ef7c6f11) sends `client.get_pr_diff(repo, number)` to Jev, and `src/devops_cli/release/merge_candidate.py:244` reads `pulls/{number}/files`. These are the two reads that the issue names.
- The merge base of a plan pull request can move. The plan fix step rebases the plan commit onto the latest default branch and force-pushes the plan branch (`src/devops_cli/roadmap/steps/fix_plan.py:488`). `devops pr update-branch` sends GitHub's `pulls/{n}/update-branch`, which merges the base branch into the head (`src/devops_cli/github/branch_update.py:36`). The update button of GitHub does the same.
- The merge base of a release pull request can move. The timeline of the release pull request of 0.127.0 holds one `head_ref_force_pushed` event, and that of 0.126.0 holds two: release-please force-pushes a new commit onto the tip of `main` when it updates the pull request.
- A live probe on 2026-11-13 of the 16 last closed pull requests of the Service App and the release App compared `compare/<base.sha>...<head>` with `compare/main...<head>`. In all 16, `base.sha` was the merge base and the two file counts were equal, so GitHub moved `base.sha` on each of those force-pushes. The stale case of #2530 came after a merge commit: `base.sha` 0137f231, merge base 5c4d24ee, 184 files against 11. So the two reads hold the defect only after a merge of the base branch into the head, and the compare read removes the dependency on GitHub moving `base.sha`.
- `devops gh api -H 'Accept: application/vnd.github.diff' 'repos/dan-petty/devops-cli/compare/main...8d08977f'` gave 7 `diff --git` lines on 2026-11-13, the same count as the pulls diff of the open plan pull request of #5272. So the compare endpoint serves the diff media type that `get_pr_diff` reads.
- `PullStatus` holds `base_ref` from `base.ref` of the payload (`src/devops_cli/github/client.py:98`), and `ReleasePull` holds `base_ref` too, so both readers know the base branch with no new request.
- `.github/workflows/release-merge.yml` gives the pick job `contents: read`, `pull-requests: read` and `checks: read`.
- Both readers read only open pull requests, so the rule of the issue for a merged pull request does not apply to them. `_settle` returns before the Jev check for a pull request that is not an open draft, and the pick lists `pulls?state=open`.
- A second live read on 2026-11-13 confirmed the release case: the timeline of the release pull request #5366 holds one `head_ref_force_pushed` event, and its `base.sha` f299667c9 is the tip of `main` when it merged.
- Item 2 cannot be built on `main` now. The pull request of #5346 is open on 2026-11-13, and only it compares `<base.ref>...<head>` in `devops review pr` and `devops ai analyze pr`. On `main`, `devops review pr` reads the pulls diff and `base.sha` (`src/devops_cli/commands/review.py:731`), and the pulls diff holds the files of a merged pull request. The item moves to #5397, which starts after that change merges.

## Existing Tool Considered

gidgethub 6.0.0 (Apache-2.0, maintained) is the GitHub REST client that ADR 0006 chooses. The GitHub session sends the compare request through it, and `GitHubClient.get_compare_files` already reads the compare. The change adds no dependency: it adds one read of the compare in the diff media type and moves two callers.
