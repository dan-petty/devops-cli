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
When the head commit of the pull request reports no check run and no commit status, and the repository has no GitHub Actions workflow, no check will start. Then `devops pr ready` SHALL say so, SHALL NOT judge the checks or warn of them, and SHALL mark the pull request ready with no `--force`.

#### Scenario: A repository with no CI
- **WHEN** the head commit reports no check and the repository has no workflow
- **THEN** `pr ready` names the repository, says that it has no GitHub Actions workflow, marks the pull request ready, and exits 0 with no warning about "no checks reported"

### Requirement: pr ready waits for checks that a workflow can start
When the head commit reports no check and the repository has a GitHub Actions workflow, `devops pr ready` SHALL wait for the checks as before. A read of the workflows that fails SHALL stop the command with exit 1 and the error.

#### Scenario: Checks that have not started
- **WHEN** the head commit reports no check and the repository has 2 workflows
- **THEN** `pr ready` exits 8 and marks nothing

#### Scenario: The workflows cannot be read
- **WHEN** the head commit reports no check and GitHub answers the read of the workflows with an error
- **THEN** `pr ready` exits 1 and marks nothing

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
