# pre-push-branch-current Specification

## Purpose
Keep each push to GitHub on a branch that holds the latest `origin/main`, so that its pull request merges with no conflict and needs no catch-up update.

## Requirements

### Requirement: The pre-push hook refuses a branch that does not hold origin/main
On a `git push` of a branch, the hook `branch-current` SHALL fetch `main` of `origin` and SHALL refuse the push when the pushed commit does not hold the fetched commit, with a message that names `git fetch origin && git rebase origin/main`. A fetch that fails SHALL refuse the push with its own message. A push of a tag and a run of the stage that is no `git push` SHALL pass.

#### Scenario: A branch behind main
- **WHEN** `main` of `origin` gains a commit that the pushed branch lacks
- **THEN** the hook exits 1 and names `git fetch origin && git rebase origin/main`

#### Scenario: A rebased branch
- **WHEN** the author rebases the branch onto `origin/main` and pushes again
- **THEN** the hook exits 0

#### Scenario: No push of a branch
- **WHEN** the push is of a tag, or `PRE_COMMIT_REMOTE_BRANCH` is not set
- **THEN** the hook exits 0
