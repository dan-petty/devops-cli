# Proposal: #4781

## Why
The implement Job commits generated documents and the archived change through `_commit_if_changed`.
No commit hook runs on those commits.
A hygiene defect in a generated or archived file can reach the pull request without a check.
Closes #4781.

## What Changes
Run the trusted commit stage on the staged changes of each commit that `_commit_if_changed` makes.
Stage the files that a fixer hook rewrites, and run the stage again.
Commit the rewritten files when the stage passes.
Stop the item with the hook output when the stage fails after the rerun.
Run the stage zero times when the checkout holds no change.
WIP commits continue to skip `_commit_if_changed`.

## Capabilities
- roadmap-implement-job/pull-request

## Impact
Documentation and archive commits pass the trusted pre-commit stage before push.
A failed hook stops the item with the hook output before it opens a pull request.

## Feasibility
The implement Job already calls `trusted_config` and `install_hook_environments`.
The function `commit_stage` is already implemented and tested in `implement_hooks.py`.
`_commit_if_changed` in `implement_run.py` can call `commit_stage` directly.

## Existing Tool Considered
pre-commit (https://github.com/pre-commit/pre-commit) is in use in the repository.
The change reuses `commit_stage` and requires no new tool.
