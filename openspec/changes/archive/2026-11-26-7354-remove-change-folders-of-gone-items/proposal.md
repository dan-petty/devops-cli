# Proposal: #7354

## Why

`openspec/changes/` on `main` holds 7 active change folders of items that will not be built in this repository. Two issues left the repository (#4530, #4600). Four issues are closed as not planned (#2144, #2526, #3236, #3485). The change of #3060 was delivered and archived on 2026-11-03, and a copy of its plan stayed in the active folder.

Each stage Job reads the issue of each active change folder. For an issue that left the repository, that read ends with `gh: HTTP 301` in a Job, so each stage Job of the repository fails at the step `plan`. `devops roadmap plan-recheck` gives `cleanup` for the folders of the closed issues. A reader takes these folders as plans that are in progress.

## What Changes

Delete the 7 active change folders:

- `4530-expose-the-argo-workflows-ui-behind`
- `4600-list-each-service-ui-on-the`
- `2144-add-scheduled-off-node-backup-and`
- `2526-the-five-defect-fixes-merged-on`
- `3236-read-only-tools-take-paths-that`
- `3485-the-coder-tier-serves-no-second`
- `3060-a-model-ladder-for-retries-with`

No source file, test or specification changes.

## Capabilities

None. The change deletes plans, and no behavior that a consumer observes changes.

## Impact

The stage Jobs of the repository read no issue that left the repository. `devops roadmap plan-recheck` names 7 folders fewer. The archived change `archive/2026-11-03-3060-a-model-ladder-for-retries-with` keeps the record of #3060.

## Feasibility

- `uv run devops gh api repos/dan-petty/devops-cli/issues/<n>` for each folder on 2026-11-26: #4530 and #4600 answer with the issue of another repository; #2144, #2526, #3236 and #3485 are closed with the reason `not_planned`; #3060 is closed with the reason `completed`.
- `ls openspec/changes/archive | grep 3060` gives `2026-11-03-3060-a-model-ladder-for-retries-with`.
- The log of the stage Job of #5289 on v0.223.2: `Could not revalidate issue #4530 in dan-petty/devops-cli (exit 1): gh api repos/dan-petty/devops-cli/issues/4530 --include; stderr: gh: HTTP 301`.
- `grep -rn` for the 7 folder names outside `openspec/changes/` finds no reader that needs them.

## Existing Tool Considered

`openspec archive` is the tool for a delivered change. It applies the delta specifications of the folder, and none of these plans was built from its active folder, so an archive would add requirements that the code does not meet. `git rm` is the tool for a plan that will not be built, as `docs/roadmap/plan-recheck.md` says for the result `cleanup`.
