# pr-monitor Specification

## Purpose
The pull-request monitor polls one pull request until its checks and reviews settle or the watch times out, and it rides out a slow GitHub read.

## Requirements

### Requirement: A failed read does not end the watch
`monitor_pr` SHALL count a failed read of the pull request as a poll with no new data, print a warning, and poll again at its interval. It SHALL stop with the last error only after three failed reads in a row, or when its timeout passes.

#### Scenario: One failed read
- **WHEN** a poll raises `GitHubOperationError` and the next poll returns a terminal status
- **THEN** the monitor returns that result and prints a warning that names the failure

#### Scenario: Three failed reads in a row
- **WHEN** three polls in a row raise `GitHubOperationError`
- **THEN** the monitor raises the last error

### Requirement: Empty check runs report pending
When a poll of a pull request reads zero check runs on a checked head, the monitor SHALL report the check status as pending rather than ready.

#### Scenario: Zero check runs on poll
- **WHEN** a pull request is polled and reports zero check runs
- **THEN** the verdict is PENDING

### Requirement: Unified pull request verdict
The watch step SHALL provide a single pure verdict function that returns PENDING, READY, FAILED, CONFLICT, BEHIND, THREADS, MERGED, CLOSED, or HEAD_MOVED.

#### Scenario: Skip CI commit message
- **WHEN** a pull request head commit message contains `[skip ci]`
- **THEN** the verdict function returns no verdict

#### Scenario: State outcomes table
- **WHEN** a pull request is in a given state
- **THEN** the verdict function returns the expected verdict enum

### Requirement: One mark-ready wrapper
The ready step SHALL be the single wrapper executing `gh pr ready`. It SHALL ask `draft_readiness` before it sends `gh pr ready`, and it SHALL verify that the remote head commit matches the expected head before transitioning.

#### Scenario: Head matches expected head
- **WHEN** `draft_readiness` answers ready and the remote pull request head SHA equals the expected head SHA
- **THEN** `mark_ready` transitions the draft to ready

### Requirement: The wrapper sends nothing that draft readiness refuses
`mark_ready` SHALL judge the draft that its caller gives, or, when the caller gives none, the draft that `read_ready_draft` reads with the check runs of the head. When `draft_readiness` does not answer ready, it SHALL raise an error with the reason and SHALL send no `gh pr ready`. Only the `--force` of a person SHALL skip the decision.

#### Scenario: An implement draft with an unticked task group
- **WHEN** a caller gives an implement draft whose task group 5 has a task that is not ticked
- **THEN** `mark_ready` raises an error that names the group and sends no `gh pr ready`

#### Scenario: A caller with no draft
- **WHEN** a caller gives no draft for a green implement pull request whose task group 5 is not ticked
- **THEN** `mark_ready` reads the pull request, the check runs of its head and its change, raises an error that names the group, and sends no `gh pr ready`

#### Scenario: The force of a person
- **WHEN** a person passes `--force`
- **THEN** `mark_ready` sends `gh pr ready` with no decision

### Requirement: Named default timeout
The project SHALL define `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` as `600` in `src/devops_cli/config/defaults.py`.

#### Scenario: Constant holds 600 seconds
- **WHEN** a unit test imports `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` from `devops_cli.config.defaults`
- **THEN** the value equals `600`

### Requirement: Monitor uses the default timeout
`monitor_pr_command`, `monitor_pr`, and `plan_pr_monitor` SHALL use `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` (`600`) as the default of `timeout` / `--timeout`.

#### Scenario: Command default matches the constant
- **WHEN** a unit test inspects the default of the `timeout` parameter of `monitor_pr_command`
- **THEN** the default equals `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` (`600`)

### Requirement: Explicit timeout override
`devops pr monitor` SHALL keep an explicit `--timeout` value instead of the default.

#### Scenario: Explicit timeout is kept
- **WHEN** a test builds or runs the dry-run plan of `devops pr monitor 42 -R owner/repo --timeout 42 --dry-run`
- **THEN** the planned monitor request reports `up to 42s` instead of `600s`

### Requirement: The monitor waits for running checks with gh pr checks --watch
While the merge-readiness verdict holds a running check, `monitor_pr` SHALL wait with `gh pr checks <number> --repo <owner>/<name> --watch --interval <interval>`, with the time left before its timeout as the time limit of the process, and SHALL read the pull request again at once when gh ends. It SHALL wait `interval` before the next watch, and before the next read when gh answers `no checks reported`.

#### Scenario: A running check
- **WHEN** the first read holds a running check, the watch exits 0, and the next read holds no running check
- **THEN** the monitor runs one watch with a time limit of 600 s, sleeps for nothing, and exits 0

#### Scenario: The watch passes the timeout
- **WHEN** a check still runs when the time limit of the watch passes
- **THEN** the monitor exits 3 and names the running check

#### Scenario: A head with no check
- **WHEN** gh answers `no checks reported` and the rules of `main` require a check
- **THEN** the monitor sleeps one interval before it reads the pull request again

#### Scenario: A check that runs after the watch
- **WHEN** a check still runs on the read after a watch that exited 0
- **THEN** the monitor sleeps one interval before it watches again
