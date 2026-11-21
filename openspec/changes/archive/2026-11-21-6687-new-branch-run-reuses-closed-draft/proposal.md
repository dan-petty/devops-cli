# Proposal: #6687

## Why

A review of #6670, the implement Job on the phases, found four defects of a `publish` that runs again, and texts that still describe the checkpoints and `OriginGit` for the implement job. Closes #6687.

## What Changes

- `prepare` always writes `implement.pr`: the pull request of the target, or none for a new branch. A new branch no longer takes the closed draft of an earlier Job.
- `_open_draft` finds the open pull request of the branch before it opens one. It updates a draft that the App opened, so a `publish` that died before the mark `implement.pr` opens no second draft and deletes no branch, and it stops at a pull request of another account and writes nothing to it.
- A withdraw that pushed clears `implement.base` at once, before the close of the draft, so a `publish` that runs again withdraws nothing a second time and returns the item to New.
- A title of the issue with a closing keyword stops the item before the push, with its own reason. `closing_keyword_in` counts only an issue reference after the keyword, so `closes #include` is no closing keyword.
- The dry-run plan lists the delete of the branch of a refused draft, the new repository and the fetch of each withdraw, and the fetch of the lease.
- SECURITY.md, the docstrings of `process_hardening.py`, `worktree_add.py` and `stop_clear.py`, the description of `continuations_per_item` and two spec texts describe the phases.

## Capabilities

- `roadmap-implement-job`: the draft mark of `prepare`, the open draft of a branch, the record of the withdraw, the title of the issue.
- `roadmap-implement-runner`: the home folder of the git calls.

## Impact

A planned item gets one more GitHub read when `publish` opens a draft: the open pull requests of its branch. No setting changes.

## Feasibility

Each defect was shown with real git and the GitHub fakes in the review of #6670, and each test of this change fails on `main` and passes with it.

## Existing Tool Considered

`open_or_update` already finds the open pull request of a head (`find_open_pull`, #5020); the change turns that lookup on. No new tool is necessary.
