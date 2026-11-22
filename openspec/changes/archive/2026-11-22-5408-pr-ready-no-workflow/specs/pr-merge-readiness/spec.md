## MODIFIED Requirements

### Requirement: pr ready does not wait for checks in a repository with no CI

When the head commit of the pull request reports no check run and no commit status, and no
workflow at that commit can start a check on the pull request, the merge readiness verdict SHALL
add no pending-check blocker and SHALL name the missing CI in an INFO advisory. `devops pr ready`
SHALL say so, SHALL NOT judge the checks or warn of them, and SHALL mark the pull request ready
with no `--force`.

#### Scenario: A repository with no CI

- **WHEN** the head commit reports no check and holds no workflow file
- **THEN** `pr ready` names the repository, says that no workflow of it can start a check on the
  pull request, marks the pull request ready, and exits 0 with no warning about "no checks
  reported"

#### Scenario: A push-only workflow

- **WHEN** the head commit reports no check and holds one workflow with only `push` and
  `workflow_dispatch` triggers
- **THEN** `pr ready` marks the pull request ready and exits 0

#### Scenario: A path filter that skips every changed file

- **WHEN** the head commit reports no check, holds one workflow whose `pull_request` event has
  `paths: [k8s/**]`, and the pull request changes only `README.md`
- **THEN** `pr ready` marks the pull request ready and exits 0

### Requirement: pr ready waits for checks that a workflow can start

When the head commit reports no check and holds a workflow that can start one on the pull
request, `devops pr ready` SHALL wait for the checks as before. A read of the workflows that fails
SHALL keep the pending check, so `devops pr ready` SHALL exit 8 and marks nothing.

#### Scenario: Checks that have not started

- **WHEN** the head commit reports no check and holds a workflow that lists `pull_request`
- **THEN** `pr ready` exits 8 and marks nothing

#### Scenario: A path filter that matches a changed file

- **WHEN** the head commit reports no check, holds one workflow whose `pull_request` event has
  `paths: [k8s/**]`, and the pull request changes `k8s/app.yaml`
- **THEN** `pr ready` exits 8 and marks nothing

#### Scenario: The workflows cannot be read

- **WHEN** the head commit reports no check and GitHub answers the read of the workflows with an
  error
- **THEN** `pr ready` exits 8 and marks nothing

### Requirement: The verdict reads the workflow triggers at the head commit

The merge-readiness verdict SHALL read `.github/workflows` at the head commit, the `on` key of
each workflow file, and the branch and path filters of each `pull_request` and
`pull_request_target` event. A 404, an empty folder, or a folder whose workflows all list other
triggers or have filters that skip the pull request SHALL mean that no CI can run on the pull
request.

#### Scenario: A pull-request workflow keeps the pending check

- **WHEN** a test gives the head commit one workflow whose `on` key lists `pull_request` and
  gives no check runs
- **THEN** the verdict holds `BlockerKind.CHECKS_PENDING` and `pending_checks` holds
  `no checks reported`

#### Scenario: A pull_request_target workflow keeps the pending check

- **WHEN** a test gives the head commit one workflow whose `on` key lists only
  `pull_request_target` and gives no check runs
- **THEN** the verdict holds `BlockerKind.CHECKS_PENDING` and `no_ci` is false

#### Scenario: A push-only workflow suppresses the pending check

- **WHEN** a test gives the head commit one workflow with only `push` and `workflow_dispatch`
  triggers and gives no check runs
- **THEN** the verdict holds no `BlockerKind.CHECKS_PENDING` blocker and holds the no-CI advisory

#### Scenario: An unread workflow fails closed

- **WHEN** a test makes the workflow read fail and gives no check runs
- **THEN** the verdict holds `BlockerKind.CHECKS_PENDING` and `pending_checks` holds
  `no checks reported`

## ADDED Requirements

### Requirement: The pull request filters of a workflow follow GitHub's rules

A workflow SHALL start a check on a pull request only when the filters of its pull request event
take it: `branches` or `branches-ignore` for the base branch, and `paths` or `paths-ignore` for
the files of the compare read, with the old path of each renamed file. The last pattern that
matches SHALL decide, and a `!` pattern SHALL exclude. Both filters SHALL take the pull request,
and no path filter SHALL take a pull request that changes no file.

#### Scenario: A paths-ignore filter that holds every changed file

- **WHEN** `starts_on_pull_request` judges a workflow whose `pull_request` event has
  `paths-ignore: ['docs/**']` for a pull request that changes only `docs/README.md`
- **THEN** it returns false

#### Scenario: A branch filter that skips the base branch

- **WHEN** `starts_on_pull_request` judges a workflow whose `pull_request` event has
  `branches: ['releases/**']` for a pull request into `main`
- **THEN** it returns false

#### Scenario: A negative pattern after a positive one

- **WHEN** `starts_on_pull_request` judges a workflow whose `pull_request` event has
  `paths: ['sub-project/**', '!sub-project/docs/**']` for a pull request that changes only
  `sub-project/docs/readme.md`
- **THEN** it returns false

#### Scenario: A file renamed out of a filtered folder

- **WHEN** the head commit reports no check, holds one workflow whose `pull_request` event has
  `paths: [k8s/**]`, and the compare lists `docs/app.yaml` as renamed from `k8s/app.yaml`
- **THEN** the verdict holds `BlockerKind.CHECKS_PENDING` and `no_ci` is false

### Requirement: A workflow filter that cannot be judged keeps the wait

A filter that the verdict cannot judge SHALL take the pull request, so the workflow can start a
check. The cases are a changed-file list that is unread or holds GitHub's limit of files of one
comparison, an unknown base branch, a filter value that is no list of strings, both forms of one
filter, and a pattern with `?`, `+` or a `**` that shares a path segment with other characters,
which GitHub reads otherwise than wcmatch.

#### Scenario: A pattern with GitHub's quantifier

- **WHEN** `starts_on_pull_request` judges a workflow whose `pull_request` event has
  `paths: ['*.jsx?']` for a pull request that changes only `page.js`
- **THEN** it returns true

#### Scenario: A file list at GitHub's limit

- **WHEN** the head commit reports no check, holds one workflow whose `pull_request` event has
  `paths: [k8s/**]`, and the compare answer holds GitHub's limit of files, none of them under
  `k8s/`
- **THEN** the verdict holds `BlockerKind.CHECKS_PENDING` and `no_ci` is false

#### Scenario: Changed files that are unread

- **WHEN** the head commit reports no check, holds one workflow whose `pull_request` event has
  `paths: [k8s/**]`, and GitHub answers the compare read with an error
- **THEN** the verdict holds `BlockerKind.CHECKS_PENDING` and `no_ci` is false
