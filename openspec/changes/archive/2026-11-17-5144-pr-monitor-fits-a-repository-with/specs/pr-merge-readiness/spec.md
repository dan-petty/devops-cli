## MODIFIED Requirements

### Requirement: pr ready does not wait for checks in a repository with no CI

When the head commit of the pull request reports no check run and no commit status, the merge
readiness verdict SHALL read the workflows at that commit and their triggers. When no workflow
lists `pull_request` or `pull_request_target`, no check can start. Then the verdict SHALL add no
pending-check blocker and SHALL name the missing CI in an INFO advisory. `devops pr ready` SHALL
say so, SHALL NOT judge the checks or warn of them, and SHALL mark the pull request ready with no
`--force`.

#### Scenario: A repository with no CI

- **WHEN** the head commit reports no check and holds no workflow file
- **THEN** `pr ready` names the repository, says that it has no workflow that runs on a pull
  request, marks the pull request ready, and exits 0 with no warning about "no checks reported"

#### Scenario: A push-only workflow

- **WHEN** the head commit reports no check and holds one workflow with only `push` and
  `workflow_dispatch` triggers
- **THEN** `pr ready` marks the pull request ready and exits 0

### Requirement: pr ready waits for checks that a workflow can start

When the head commit reports no check and holds a workflow that lists `pull_request` or
`pull_request_target`, `devops pr ready` SHALL wait for the checks as before. A read of the
workflows that fails SHALL keep the pending check, so `devops pr ready` SHALL exit 8 and marks
nothing.

#### Scenario: Checks that have not started

- **WHEN** the head commit reports no check and holds a workflow that lists `pull_request`
- **THEN** `pr ready` exits 8 and marks nothing

#### Scenario: The workflows cannot be read

- **WHEN** the head commit reports no check and GitHub answers the read of the workflows with an
  error
- **THEN** `pr ready` exits 8 and marks nothing

## ADDED Requirements

### Requirement: The verdict reads the workflow triggers at the head commit

The merge-readiness verdict SHALL read `.github/workflows` at the head commit and the `on` key of
each workflow file. A 404, an empty folder, or a folder whose workflows all list other triggers
SHALL mean that no CI can run on the pull request.

#### Scenario: A pull-request workflow keeps the pending check

- **WHEN** a test gives the head commit one workflow whose `on` key lists `pull_request` and
  gives no check runs
- **THEN** the verdict holds `BlockerKind.CHECKS_PENDING` and `pending_checks` holds
  `no checks reported`

#### Scenario: A push-only workflow suppresses the pending check

- **WHEN** a test gives the head commit one workflow with only `push` and `workflow_dispatch`
  triggers and gives no check runs
- **THEN** the verdict holds no `BlockerKind.CHECKS_PENDING` blocker and holds the no-CI advisory

#### Scenario: An unread workflow fails closed

- **WHEN** a test makes the workflow read fail and gives no check runs
- **THEN** the verdict holds `BlockerKind.CHECKS_PENDING` and `pending_checks` holds
  `no checks reported`

### Requirement: check-readiness reports a repository with no CI

`devops pr check-readiness` SHALL exit 0 with the no-CI advisory when no workflow can run on the
head commit and no other blocker applies.

#### Scenario: check-readiness on a repository with no CI

- **WHEN** a test runs `devops pr check-readiness` for a pull request whose head commit holds no
  workflow and no check
- **THEN** the test asserts exit code 0 and that the output contains the no-CI advisory

### Requirement: pr monitor does not wait for a repository with no CI

`devops pr monitor` SHALL settle on its first poll when no workflow can run on the head commit
and no other blocker applies.

#### Scenario: pr monitor on a repository with no CI

- **WHEN** a test runs `devops pr monitor` with a fake clock for a pull request whose head commit
  holds no workflow and no check
- **THEN** the test asserts exit code 0 and that the monitor made no sleep call

### Requirement: pr monitor stops on a conflict before pending checks

`devops pr monitor` SHALL report a merge conflict and stop before it waits on the pending
no-checks stand-in.

#### Scenario: Conflict with no checks

- **WHEN** a test gives the verdict a `mergeable_state` of `dirty` and no check runs
- **THEN** the output names the merge conflict and the monitor made no sleep call
