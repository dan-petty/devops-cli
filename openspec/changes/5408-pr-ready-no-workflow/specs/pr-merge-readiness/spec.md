## MODIFIED Requirements

### Requirement: pr ready does not wait for checks in a repository with no CI

When the head commit of the pull request reports no check run and no commit status, the merge
readiness verdict SHALL read the workflows at that commit, their triggers and the filters of each
pull request trigger. A workflow can start a check when it lists `pull_request` or
`pull_request_target` and the filters of that event take the pull request: `branches` or
`branches-ignore` for the base branch, and `paths` or `paths-ignore` for the files that the pull
request changes. The filters SHALL follow the rules that GitHub documents: the last pattern that
matches decides, a pattern that starts with `!` excludes, both filters must take the pull
request, and a pull request that changes no file is taken by no path filter. When no workflow can
start a check, the verdict SHALL add no pending-check blocker and SHALL name the missing CI in an
INFO advisory. `devops pr ready` SHALL say so, SHALL NOT judge the checks or warn of them, and
SHALL mark the pull request ready with no `--force`.

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

### Requirement: pr ready waits for checks that a workflow can start

When the head commit reports no check and holds a workflow that can start one, `devops pr ready`
SHALL wait for the checks as before. A `pull_request_target` trigger SHALL count as a pull request
trigger. A filter that the verdict cannot judge SHALL take the pull request, so the workflow can
start a check: the changed files are unread, or their list holds GitHub's limit of files of one
comparison; the payload names no base branch; a filter value is no list of strings; a workflow
sets both forms of one filter; or a pattern holds `?` or `+`, or a `**` that shares a path segment
with other characters, which GitHub reads as quantifiers and as any characters. A read of the
workflows that fails SHALL keep the pending check, so `devops pr ready` SHALL exit 8 and marks
nothing.

#### Scenario: Checks that have not started

- **WHEN** the head commit reports no check and holds a workflow that lists `pull_request`
- **THEN** `pr ready` exits 8 and marks nothing

#### Scenario: A path filter that matches a changed file

- **WHEN** the head commit reports no check, holds one workflow whose `pull_request` event has
  `paths: [k8s/**]`, and the pull request changes `k8s/app.yaml`
- **THEN** `pr ready` exits 8 and marks nothing

#### Scenario: A pull_request_target workflow

- **WHEN** the head commit reports no check and its only workflow lists `pull_request_target`
- **THEN** the verdict holds a pending-check blocker and `no_ci` is false

#### Scenario: A pattern with GitHub's quantifier

- **WHEN** `starts_on_pull_request` judges a workflow whose `pull_request` event has
  `paths: ['*.jsx?']` for a pull request that changes only `page.js`
- **THEN** it returns true

#### Scenario: A file list at GitHub's limit

- **WHEN** the head commit reports no check, holds one workflow whose `pull_request` event has
  `paths: [k8s/**]`, and the compare answer holds GitHub's limit of files, none of them under
  `k8s/`
- **THEN** the verdict holds a pending-check blocker and `no_ci` is false

#### Scenario: The workflows cannot be read

- **WHEN** the head commit reports no check and GitHub answers the read of the workflows with an
  error
- **THEN** `pr ready` exits 8 and marks nothing
