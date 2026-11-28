## ADDED Requirements

### Requirement: The verdict reads the checks with gh pr checks

The merge-readiness verdict SHALL read the checks of the pull request with
`gh pr checks <number> --repo <owner>/<name> --json name,state,bucket,workflow,link`, and SHALL
judge each check that gh lists with the bucket that gh gives. The gh answer `no checks reported`
SHALL read as the pending stand-in `no checks reported`. Each other failed read SHALL be one
`BlockerKind.CHECKS_UNREAD` blocker that names the cause.

#### Scenario: A failed check

- **WHEN** gh lists CodeQL in the bucket `fail` and CI in the bucket `pass`
- **THEN** the verdict holds the one blocker "PR #335 has 1 failing check(s): CodeQL." and sends
  `gh pr checks 335 --repo dan-petty/devops-cli --json name,state,bucket,workflow,link`

#### Scenario: gh cannot read the checks

- **WHEN** `gh pr checks` exits 1 with `HTTP 502` on stderr
- **THEN** the verdict holds one `BlockerKind.CHECKS_UNREAD` blocker that names `HTTP 502`

#### Scenario: A cancelled check

- **WHEN** gh lists zizmor in the bucket `cancel` and audit in the bucket `fail`
- **THEN** the verdict holds the one blocker "PR #335 has 2 failing check(s): audit, zizmor."

#### Scenario: gh prints no list

- **WHEN** `gh pr checks` exits 0 and prints a JSON object
- **THEN** the verdict holds one `BlockerKind.CHECKS_UNREAD` blocker

### Requirement: pr ready waits for checks that the base branch requires

When gh answers `no checks reported` and the rules of the base branch hold a
`required_status_checks` rule, the verdict SHALL keep the pending stand-in, and `devops pr ready`
SHALL exit 8 and mark nothing. A read of the rules that fails SHALL keep the pending stand-in too.

#### Scenario: Required checks that have not started

- **WHEN** gh answers `no checks reported` and the rules of `main` require the check CI
- **THEN** `pr ready` exits 8 and marks nothing

#### Scenario: The rules cannot be read

- **WHEN** gh answers `no checks reported` and GitHub answers the read of the rules of `main`
  with HTTP 403
- **THEN** `pr ready` exits 8 and marks nothing

## MODIFIED Requirements

### Requirement: pr ready does not wait for checks in a repository with no CI

When gh answers `no checks reported` for the pull request, and the rules of its base branch hold
no `required_status_checks` rule, the merge readiness verdict SHALL add no pending-check blocker
and SHALL name the missing CI in an INFO advisory. GitHub merges such a pull request with no
check. `devops pr ready` SHALL say so, SHALL NOT judge the checks or warn of them, and SHALL mark
the pull request ready with no `--force`.

#### Scenario: A repository with no CI

- **WHEN** gh answers `no checks reported` and the rules of `main` hold no
  `required_status_checks` rule
- **THEN** `pr ready` names the repository, says that the rules of `main` require no check,
  marks the pull request ready, and exits 0 with no warning about "no checks reported"

#### Scenario: A push-only workflow

- **WHEN** the only workflow of the repository has `push` and `workflow_dispatch` triggers, so gh
  answers `no checks reported`, and the rules of `main` require no check
- **THEN** `pr ready` marks the pull request ready and exits 0

#### Scenario: A path filter that skips every changed file

- **WHEN** the `paths` filter of the `pull_request` workflow skips every changed file, so gh
  answers `no checks reported`, and the rules of `main` require no check
- **THEN** `pr ready` marks the pull request ready and exits 0

### Requirement: check-readiness reports a repository with no CI

`devops pr check-readiness` SHALL exit 0 with the no-CI advisory when gh answers
`no checks reported`, the rules of the base branch require no check, and no other blocker applies.

#### Scenario: check-readiness on a repository with no CI

- **WHEN** a test runs `devops pr check-readiness` for a pull request whose head reports no check
  and whose base branch rules require no check
- **THEN** the test asserts exit code 0 and that the output contains the no-CI advisory

### Requirement: pr monitor does not wait for a repository with no CI

`devops pr monitor` SHALL settle on its first poll when gh answers `no checks reported`, the rules
of the base branch require no check, and no other blocker applies.

#### Scenario: pr monitor on a repository with no CI

- **WHEN** a test runs `devops pr monitor` with a fake clock for a pull request whose head
  reports no check and whose base branch rules require no check
- **THEN** the test asserts exit code 0 and that the monitor made no sleep call

### Requirement: Only the latest run of each check counts
`read_check_runs`, the REST reader of the roadmap readiness rows, SHALL keep only the latest run of each check, whatever its conclusion. A check SHALL be the name of the run and the id of the app that reports it. The time of a run SHALL be its `started_at`, else its `completed_at`. A run with no time, and each run at the latest time of its check, SHALL stay.

#### Scenario: A newer run passes after an older run failed
- **WHEN** the head commit has a failed run of Fail-to-Pass Check and a newer passed run of it in another check suite
- **THEN** `read_check_runs` keeps only the passed run

#### Scenario: A newer run fails after an older run passed
- **WHEN** the head commit has a passed run of Fail-to-Pass Check and a newer failed run of it
- **THEN** `read_check_runs` keeps only the failed run, and the checks do not pass

#### Scenario: A newer run still runs
- **WHEN** a check has a passed run and a newer run that still runs
- **THEN** the check is pending

#### Scenario: Two apps report a check of one name
- **WHEN** one app reports a failed run of a check, and another app reports a newer passed run of a check with the same name
- **THEN** both runs stay, and the checks do not pass

## REMOVED Requirements

### Requirement: pr ready waits for checks that a workflow can start
**Reason**: The verdict no longer reads the workflow files. The rules of the base branch decide whether a head with no check waits (#7508).
**Migration**: The requirement "pr ready waits for checks that the base branch requires" of this capability gives the wait.

### Requirement: The verdict reads the workflow triggers at the head commit
**Reason**: `workflow_triggers.py` and `GitHubClient.pull_request_workflow_at` are deleted. GitHub, not a copy of its filters, decides which checks run (#7508).
**Migration**: The requirement "The verdict reads the checks with gh pr checks" of this capability gives the read.

### Requirement: The pull request filters of a workflow follow GitHub's rules
**Reason**: `starts_on_pull_request` is deleted with `workflow_triggers.py` (#7508).
**Migration**: None. A repository that needs a wait for a check makes the check required in the rules of its base branch.

### Requirement: A workflow filter that cannot be judged keeps the wait
**Reason**: No workflow filter is judged (#7508).
**Migration**: The requirement "pr ready waits for checks that the base branch requires" of this capability keeps the wait when the rules cannot be read.
