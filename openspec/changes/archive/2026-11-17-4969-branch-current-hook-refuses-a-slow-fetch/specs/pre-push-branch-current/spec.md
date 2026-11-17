## MODIFIED Requirements

### Requirement: The pre-push hook refuses a branch that does not hold origin/main

On a `git push` of a branch, the hook `branch-current` SHALL fetch `main` of `origin` with a 24
second limit and SHALL refuse the push when the pushed commit does not hold the fetched commit,
with a message that names `git fetch origin && git rebase origin/main`. A fetch that fails SHALL
refuse the push with its own message. A push of a tag and a run of the stage that is no `git push`
SHALL pass.

#### Scenario: A branch behind main

- **WHEN** `main` of `origin` gains a commit that the pushed branch lacks
- **THEN** the hook exits 1 and names `git fetch origin && git rebase origin/main`

#### Scenario: A rebased branch

- **WHEN** the author rebases the branch onto `origin/main` and pushes again
- **THEN** the hook exits 0

#### Scenario: No push of a branch

- **WHEN** the push is of a tag, or `PRE_COMMIT_REMOTE_BRANCH` is not set
- **THEN** the hook exits 0

## ADDED Requirements

### Requirement: A fetch timeout names its limit

When the fetch exits with status 124, the hook SHALL say that it stopped the fetch after 24 seconds
and SHALL NOT say that origin is unavailable. When the fetch exits with another status, the hook
SHALL say that origin is unavailable. The sum of the time limits of the pre-push hooks SHALL stay
below the 120 second limit of the agent shell.

#### Scenario: The fetch runs out of time

- **WHEN** the fetch exits with status 124
- **THEN** the hook prints a message that names 24 seconds and exits 1, and the message does not
  say that origin is unavailable

#### Scenario: The fetch fails

- **WHEN** the fetch exits with status 128
- **THEN** the hook prints the unavailable-origin message and exits 1

#### Scenario: The time limits add up

- **WHEN** the time limits of the pre-push hooks are summed
- **THEN** the sum is less than 120 seconds
