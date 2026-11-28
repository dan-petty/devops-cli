# Design

## Decisions

- **Watch all checks: no `--required`.**: The verdict judges all checks (#7508), so a watch of the 3 required checks of 29 (PR #7481) would end while the others still run, and the monitor would read a running check again at once.
- **No `--fail-fast`.**: The monitor waits until no check runs and then names every blocker (#998, `test_the_monitor_waits_for_the_checks_and_names_every_blocker`). With `--fail-fast`, gh ends at the first failure while other checks run (`if opts.FailFast && counts.Failed > 0 { break }` in `checks.go`), so the report would miss a later failure.
- **The time limit of the watch is the time left before the monitor's timeout, with no retry.**: gh has no time limit of its own. `run_gh` stops the process and answers `CONST_GH_TIMEOUT_EXIT_CODE`, which gives the timeout result. A retry would pass the timeout.
- **After a watch, read at once; watch again only after an interval.**: A watch that gh ends at once, such as a check that starts after the watch, can then never repeat with no pause.
- **Keep the read each interval for a head with no check, an active Copilot review and the settle time.**: gh ends a watch at once with `no checks reported`, and `gh pr checks` reads only the check rollup, not the reviews.
- **Do not keep the output of gh.**: gh prints a table on each read. The monitor reads the verdict after the watch and prints one result, in the format that `--format` names (AGENTS.md rule 13).

## Rejected alternatives

- **`gh pr checks --watch --fail-fast`, as #7509 first proposed.**: It ends at the first failure while other checks run, which breaks the #998 rule that the monitor names every blocker once. A second watch would also end at once on the same failure, a loop with no pause.
- **`gh pr checks --watch --required`.**: It waits for 3 of the 29 checks of PR #7481, while the verdict judges all of them.
- **Keep the poll of the verdict each interval.**: Each poll read the pull request, the checks, the review threads, the compare of the files, the closing issues and the reviews. The watch reads only the checks, with one GraphQL query each interval.
- **Show the table of gh on the terminal.**: The JSON, YAML and Markdown formats print one result, and an agent reads the output (AGENTS.md rule 13).

## Known limits

- The pacing ledger of `run_gh` counts the watch as one request. gh sends its own GraphQL query each interval, which the ledger does not see.
- The monitor sees a merge or a close during a watch only after the watch ends.
