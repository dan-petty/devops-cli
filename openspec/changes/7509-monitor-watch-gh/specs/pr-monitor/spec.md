## ADDED Requirements

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
