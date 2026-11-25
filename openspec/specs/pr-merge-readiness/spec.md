# pr-merge-readiness Specification

## Purpose
How `devops pr ready` and `devops pr monitor` judge a pull request from the one merge-readiness verdict that `devops pr check-readiness` prints, and map it to their exit codes.

## Requirements

### Requirement: The monitor waits until the checks settle and names every blocker
`devops pr monitor` SHALL keep waiting while a check of the head commit runs, whatever other blockers it sees. When no check runs, it SHALL return once, naming every blocker, and SHALL exit 1 when a check failed or could not be read, 2 for any other blocker, 0 with no blocker, and 3 when its timeout passes first. A merged pull request SHALL exit 0 and a closed unmerged pull request SHALL exit 2, whatever blockers it holds.

#### Scenario: A check fails after an open thread is first seen
- **WHEN** the head commit has two running checks and one unresolved review thread, and on the next poll one check passed and the other failed
- **THEN** the monitor reads the pull request twice, exits 1, and names the failed check and the thread

#### Scenario: The checks still run at the timeout
- **WHEN** a check of the head commit still runs when the timeout passes
- **THEN** the monitor exits 3 and names the running check

#### Scenario: Closed without merge during monitoring
- **WHEN** a poll reads the state closed and merged false
- **THEN** the monitor exits 2 and names no check

### Requirement: The monitor and pr ready map the verdict to their exit codes
`devops pr monitor` and `devops pr ready` SHALL judge a pull request through the merge-readiness verdict. `devops pr ready` SHALL exit 1 when a check failed or could not be read and 8 while a check runs, and SHALL print each other blocker as a warning and mark the pull request ready.

#### Scenario: The exit codes
- **WHEN** the pull request is ready, has a running check, a failed check, unread checks, an unresolved review thread, or is a draft
- **THEN** `pr ready` exits 0, 8, 1, 1, 0 and 0, and `pr monitor` exits 0, 3, 1, 1, 2 and 2

#### Scenario: A missing priority label does not stop pr ready
- **WHEN** a draft pull request with passing checks closes an issue that holds no `priority/*` label
- **THEN** `pr ready` prints the blocker as a warning, marks the pull request ready, and exits 0

### Requirement: A pull request that cannot be read stops pr ready
`devops pr ready` SHALL stop with exit 1 and name the error when it cannot read the pull request, unless `--force` is given.

#### Scenario: The read fails
- **WHEN** GitHub answers the read of the pull request with an error
- **THEN** `pr ready` exits 1, names the error, and does not mark the pull request ready

### Requirement: A branch behind its base is no blocker
No readiness command SHALL block a pull request because its branch is behind its base.

#### Scenario: The branch is behind
- **WHEN** GitHub reports `mergeable: true` and `mergeable_state: behind`, and nothing else blocks
- **THEN** the verdict has no blocker

### Requirement: pr ready asks the readiness function
`devops pr ready` SHALL ask `draft_readiness` for the pull request, with the word of the author given. It SHALL exit 1 for a refusal and name each unticked task group of an implement pull request, and SHALL exit 8 for a wait. `--force` SHALL skip the question. A read of the item that fails SHALL stop the command with exit 1 and the error.

#### Scenario: A partial implement pull request
- **WHEN** a person runs `devops pr ready` for a draft whose item holds `implement.pr` of it and whose `tasks.md` has an unticked group 2
- **THEN** the command exits 1, prints group 2, and marks nothing

#### Scenario: The exit codes of the checks stay
- **WHEN** the draft has a running check, a failed check, or unread checks
- **THEN** the command exits 8, 1 and 1

#### Scenario: A branch with no item
- **WHEN** the head branch names no issue and the checks pass
- **THEN** the command marks the pull request ready as before

#### Scenario: The record cannot be read
- **WHEN** GitHub refuses the read of the item that the head branch names
- **THEN** the command exits 1 with the error, and `--force` marks the pull request ready

### Requirement: check-readiness names the unticked group
`devops pr check-readiness` SHALL add one blocker and exit non-zero when `draft_readiness` refuses an implement pull request, and the blocker SHALL name each unticked task group. It SHALL add none for a pull request with no recorded item. A read of the item that fails SHALL be a blocker that names the error.

#### Scenario: A partial implement pull request blocks
- **WHEN** a user runs `devops pr check-readiness` for an implement pull request with an unticked group
- **THEN** the command exits non-zero and prints the name of the group

#### Scenario: A complete implement pull request
- **WHEN** every group of the archived `tasks.md` is ticked and the other rules pass
- **THEN** the command adds no readiness blocker

#### Scenario: A pull request with no recorded item
- **WHEN** the head branch names no issue
- **THEN** the command adds no readiness blocker and reads no item

### Requirement: A pull request body must keep the form
`devops pr check-readiness` SHALL call `body_problems` on the body of the pull request, where the base holds `openspec/changes/` and the title is no plan title. A body that GitHub reports as `null` SHALL count as empty. The command SHALL exit 1 when `body_problems` returns at least one problem.

#### Scenario: A body with no closing line
- **WHEN** the body has no line `Closes #<issue>` and nothing else blocks the pull request
- **THEN** `devops pr check-readiness` prints the missing-`Closes` problem and exits 1

#### Scenario: A body in the form
- **WHEN** the body keeps the form and nothing else blocks the pull request
- **THEN** `devops pr check-readiness` prints the success line and exits 0

#### Scenario: A base without change folders
- **WHEN** the base holds no `openspec/changes/`
- **THEN** the verdict holds no body blocker

#### Scenario: A plan pull request
- **WHEN** the title is a plan title
- **THEN** the verdict holds no blocker of the kind body form

### Requirement: Every problem of the body is one blocker
The verdict SHALL hold one blocker of the kind body form for each problem that `body_problems` returns, in its order. Each blocker SHALL name the pull request number and hold the text of the problem.

#### Scenario: A body with two problems
- **WHEN** the body has no line `Closes #<issue>` and no line `Change:`
- **THEN** the verdict holds two blockers of the kind body form, one for each missing line

#### Scenario: A long body
- **WHEN** the text of the body is longer than 1,000 characters
- **THEN** the verdict holds a blocker of the kind body form that names the length and the limit

### Requirement: One conflict judgment
`devops pr check-readiness`, the implement watch and the Service row `pr_conflicts` SHALL judge a merge conflict with the one function `merge_conflict`. It SHALL return True when `mergeable` is false or the state is `dirty` or `conflicting`, None when `mergeable` is null or the state is `unknown` or empty, and False else.

#### Scenario: The row and check-readiness on one pull request
- **WHEN** the pull request payload holds `mergeable` false with `mergeable_state` `dirty`
- **THEN** `merge_conflict` reports a conflict and the row posts the conflict comment

#### Scenario: A pull request that is only behind
- **WHEN** the pull request payload holds `mergeable` true with `mergeable_state` `behind`
- **THEN** `merge_conflict` reports no conflict and the row posts no comment

#### Scenario: A state that GitHub has not computed
- **WHEN** the pull request payload holds `mergeable` null with `mergeable_state` `unknown`
- **THEN** `merge_conflict` returns None and the row posts no comment

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

### Requirement: Readiness reads the file list at the merge base
The command `devops pr check-readiness` SHALL read the files a pull request changes from the compare endpoint of the tip of the base branch and the head commit, and MUST NOT compare from the `base.sha` of the pull request payload.

#### Scenario: A moved merge base
- **WHEN** The pull request branch holds a merge commit that moves its merge base, and the payload's `base.sha` and the pulls files endpoint still name the old base.
- **THEN** The readiness read asks for the compare of the base branch and the head commit, judges the files of that answer, and no compare request of the run names the payload's `base.sha`.

#### Scenario: No pulls files request
- **WHEN** The readiness run reads the changed files of a pull request.
- **THEN** No request path of the run ends with the pulls files path, and the verdict holds no grounding blocker that names an archived change folder of another issue.

### Requirement: The compare names the head by its commit sha
The command `devops pr check-readiness` SHALL name the compare's head by the head commit sha, also when the head repository differs from the base repository.

#### Scenario: A pull request from a fork
- **WHEN** The pull request payload gives a head repository that is not the base repository.
- **THEN** The compare request names the head by its commit sha, the commit whose checks the run reads.

### Requirement: A compare answer at the file limit is reported
The command `devops pr check-readiness` SHALL report a compare answer that holds GitHub's limit of 300 files as a possibly truncated file list, and SHALL name that limit.

#### Scenario: The compare answer holds 300 files
- **WHEN** The compare endpoint returns exactly 300 files.
- **THEN** The readiness output names GitHub's limit of 300 files and holds no grounding blocker that names a change folder missing from the list.

#### Scenario: The rules that read no file still apply
- **WHEN** The compare endpoint returns exactly 300 files, the body has no `Closes` line, and the pull request closes two issues.
- **THEN** The verdict holds the blockers of the body form and of the closing issues beside the one blocker that names the limit.

#### Scenario: No suppression is named for a partial list
- **WHEN** The compare endpoint returns exactly 300 files, one of them is a path that a review.toml suppression covers, and the base keeps no change folders.
- **THEN** The verdict names no suppression and holds one warning that names the limit.

#### Scenario: An implement draft at the limit
- **WHEN** The compare answer of an implement pull request holds exactly 300 files.
- **THEN** The draft readiness refuses the pull request with a reason that names GitHub's limit of 300 files.

### Requirement: The monitor reads the pull request state on every poll
The command `devops pr monitor` SHALL read the pull request `state` on every poll and SHALL make no further poll once it reads a merged or a closed pull request.

#### Scenario: Closed during monitoring
- **WHEN** A poll reads the state closed and merged false, and the settle time has not passed.
- **THEN** The monitor makes no further poll, reads no check and no review, and returns the closed result.

#### Scenario: Merged during monitoring
- **WHEN** A poll reads merged true, and the settle time has not passed.
- **THEN** The monitor makes no further poll, reads no check and no review, and returns the merged result.

### Requirement: The monitor reports a terminal pull request with no check count
The command `devops pr monitor` SHALL report a merged or a closed pull request in one line naming its state, with no check count and no ready line.

#### Scenario: Merged output
- **WHEN** A poll reads merged true.
- **THEN** The output holds `PR #<number> is merged.`, holds no `Checks:` line and no `READY FOR MERGING`, and the exit code is 0.

#### Scenario: Closed output
- **WHEN** A poll reads the state closed and merged false.
- **THEN** The output holds `PR #<number> is closed.`, holds no `Checks:` line and no `READY FOR MERGING`, and the exit code is 2.

### Requirement: The markdown names a merged pull request as merged
The command `devops pr monitor --format markdown` SHALL name a merged pull request as merged and a closed unmerged pull request as closed, and MUST NOT call either ready.

#### Scenario: Markdown of a merged pull request
- **WHEN** The monitor's result is a merged pull request and the format is markdown.
- **THEN** The state line is `**State**: merged`, and the exit code is 0.

#### Scenario: Markdown of a closed pull request
- **WHEN** The monitor's result is a closed unmerged pull request and the format is markdown.
- **THEN** The state line is `**State**: closed`, and the exit code is 2.

### Requirement: The check-readiness plan lists the compare request
The command `devops pr check-readiness --dry-run` SHALL list the compare request that reads the file list and MUST NOT list the pulls files request.

#### Scenario: Request plan of check-readiness
- **WHEN** The dry-run plan of the command is rendered.
- **THEN** The plan holds a request whose target is `compare/<base-ref>...<head-sha>`, and holds no target that ends with the pulls files path.

### Requirement: Only the latest run of each check counts
The reader of the check runs of a commit SHALL keep only the latest run of each check, whatever the conclusion of that run. A check SHALL be the name of the run and the id of the app that reports it. The time of a run SHALL be its `started_at`, else its `completed_at`. A run with no time, and each run at the latest time of its check, SHALL stay. `devops pr ready`, `devops pr check-readiness` and the roadmap readiness rows SHALL judge the checks through this reader.

#### Scenario: A newer run passes after an older run failed
- **WHEN** the head commit has a failed run of Fail-to-Pass Check and a newer passed run of it in another check suite, and the latest run of each other check passed or was skipped
- **THEN** `devops pr ready` marks the pull request ready and exits 0, and `devops pr check-readiness` exits 0

#### Scenario: A newer run fails after an older run passed
- **WHEN** the head commit has a passed run of Fail-to-Pass Check and a newer failed run of it
- **THEN** `devops pr ready` and `devops pr check-readiness` both exit 1 and name Fail-to-Pass Check

#### Scenario: A newer run still runs
- **WHEN** a check has a passed run and a newer run that still runs
- **THEN** the check is pending

#### Scenario: Two apps report a check of one name
- **WHEN** one app reports a failed run of a check, and another app reports a newer passed run of a check with the same name
- **THEN** both runs stay, and the checks do not pass

### Requirement: A stage change states its eval evidence
A pull request that changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_criteria.py`, `src/devops_cli/roadmap/stage_eval_gates.py` or `src/devops_cli/roadmap/stage_move.py` SHALL state the stage eval evidence in its body, and the readiness verdict SHALL block the merge when it does not.

#### Scenario: A stage change with no evidence is not ready
- **WHEN** a pull request changes `src/devops_cli/roadmap/stage_change.py` and its body holds no stage eval evidence
- **THEN** the verdict holds one blocker of the kind `stage_eval` that names the path and the command

#### Scenario: A replay with two numbers is ready
- **WHEN** a pull request changes `src/devops_cli/roadmap/stage_eval_gates.py` and its body holds `uv run devops roadmap eval stage --replay` with a number before and after
- **THEN** the verdict holds no blocker

#### Scenario: A live run with one model and two scores is ready
- **WHEN** a pull request changes `src/devops_cli/roadmap/stage_move.py` and its body holds `uv run devops roadmap eval stage --model <name>` and a score before and after
- **THEN** the verdict holds no blocker

### Requirement: The evidence holds a number beside each word and one model
The stage eval evidence SHALL hold a number beside `before` and beside `after`, and a live run SHALL name exactly one model in a `--model` flag. A body with no number, one number, two different models, or a `--model` flag with no name SHALL be refused.

#### Scenario: One number is refused
- **WHEN** the body holds the replay command and a number after `before` but none after `after`
- **THEN** `stage_eval_problems` names the missing number

#### Scenario: Two models are refused
- **WHEN** the body holds two live commands with two different `--model` names
- **THEN** `stage_eval_problems` names more than one model

#### Scenario: A model flag with no name is refused
- **WHEN** the body holds `--model` with no name
- **THEN** `stage_eval_problems` names the flag

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

### Requirement: Stage plan title wins a collision
When `implement.pr` and `stage.pr` hold the same pull request number, `kind_of` SHALL return `DraftKind.STAGE_PLAN` if the pull request title starts with `docs(spec): plan` or legacy `docs(openspec): plan`.

#### Scenario: Colliding plan title
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request and a title that starts with `docs(spec): plan` or `docs(openspec): plan`
- **THEN** it returns `DraftKind.STAGE_PLAN`.

### Requirement: Implement title keeps a collision as implement
When `implement.pr` and `stage.pr` hold the same pull request number, `kind_of` SHALL return `DraftKind.IMPLEMENT` if the title does not start with `docs(spec): plan` or `docs(openspec): plan`.

#### Scenario: Colliding implement title
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request and a title that starts with `fix(roadmap): keep the last comment`
- **THEN** it returns `DraftKind.IMPLEMENT`.

#### Scenario: Colliding with no title
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request and no title is given
- **THEN** it returns `DraftKind.IMPLEMENT`.

### Requirement: Read draft preserves stage plan classification
`read_draft` SHALL classify a pull request as `DraftKind.STAGE_PLAN` when its title starts with `docs(spec): plan` or `docs(openspec): plan` and both `implement.pr` and `stage.pr` hold its number.

#### Scenario: Read draft for a colliding plan
- **WHEN** `read_draft` runs for a pull request whose title starts with `docs(spec): plan` and whose number both records hold
- **THEN** the returned `Draft.kind` is `DraftKind.STAGE_PLAN`.

### Requirement: A payload with no head commit fails closed
`assess_merge_readiness` SHALL hold a `checks_unread` blocker when the pull request payload gives no head commit SHA, and SHALL NOT report the pull request ready. `devops pr monitor` SHALL report such a poll as not ready, with `checks_failed` set and exit code 1.

#### Scenario: Payload with no head SHA
- **WHEN** the payload of the pull request holds no `head.sha`
- **THEN** the verdict holds `BlockerKind.CHECKS_UNREAD`, `is_ready` is False, and the first blocker text starts with `PR #<n> check verification failed closed:`

#### Scenario: Monitor poll with no head SHA
- **WHEN** `get_pr_monitoring_status` reads a pull request payload with no `head.sha`
- **THEN** the status holds `checks_failed` True and a non-empty `blockers`, and the settled result holds `success` False and `exit_code` 1

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
