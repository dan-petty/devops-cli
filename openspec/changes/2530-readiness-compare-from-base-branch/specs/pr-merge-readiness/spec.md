## ADDED Requirements

### Requirement: Readiness reads the file list at the merge base
The command `devops pr check-readiness` SHALL read the files a pull request changes from the compare endpoint of the tip of the base branch and the head commit, and MUST NOT compare from the `base.sha` of the pull request payload.

#### Scenario: A moved merge base
- **WHEN** The pull request branch holds a merge commit that moves its merge base, and the payload's `base.sha` and the pulls files endpoint still name the old base.
- **THEN** The readiness read asks for the compare of the base branch and the head commit, judges the files of that answer, and no request of the run names the payload's `base.sha`.

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

### Requirement: The monitor reads the pull request state on every poll
The command `devops pr monitor` SHALL read the pull request `state` on every poll and SHALL make no further poll once it reads a merged or a closed pull request.

#### Scenario: Closed during monitoring
- **WHEN** A poll reads the state closed and merged false.
- **THEN** The monitor makes no further poll and returns the closed result.

#### Scenario: Merged during monitoring
- **WHEN** A poll reads merged true.
- **THEN** The monitor makes no further poll and returns the merged result.

### Requirement: The monitor reports a terminal pull request with no check count
The command `devops pr monitor` SHALL report a merged or a closed pull request in one line naming its state, with no check count and no ready line.

#### Scenario: Merged output
- **WHEN** A poll reads merged true.
- **THEN** The output holds `PR #<number> is merged.`, holds no `Checks:` line and no `READY FOR MERGING`, and the exit code is 0.

#### Scenario: Closed output
- **WHEN** A poll reads the state closed and merged false.
- **THEN** The output holds `PR #<number> is closed.`, holds no `Checks:` line and no `READY FOR MERGING`, and the exit code is 2.

### Requirement: The markdown names a merged pull request as merged
The command `devops pr monitor --format markdown` SHALL name a merged pull request as merged and MUST NOT call it ready.

#### Scenario: Markdown of a merged pull request
- **WHEN** The monitor's result is a merged pull request and the format is markdown.
- **THEN** The state line names the pull request merged and holds no ready-for-merging text.

### Requirement: The check-readiness plan lists the compare request
The command `devops pr check-readiness --dry-run` SHALL list the compare request that reads the file list and MUST NOT list the pulls files request.

#### Scenario: Request plan of check-readiness
- **WHEN** The dry-run plan of the command is rendered.
- **THEN** The plan holds a request whose target is `compare/<base-ref>...<head-sha>`, and holds no target that ends with the pulls files path.

## MODIFIED Requirements

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
