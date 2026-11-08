# Design

## Decisions

- **State the budget's subject in `docs/TESTING.md` and add no pytest option.**: The full suite already runs on every logical CPU through the addopts of `pyproject.toml`, so `-n auto` renames the worker count, and the 6m 53s run of the issue already used that command.
- **Keep the 300-second budget on the mean of the `Tests & Coverage` check.**: `docs/TESTING.md` gives the mean over the last 20 pushes to `main` as the subject, and `devops ci job-time` fails when that mean passes the budget.
- **Add no test that bounds the pytest step's elapsed time.**: `docs/TESTING.md` forbids an upper bound on elapsed time, because a loaded machine stretches the time and the bound then fails correct code, and the ast-grep rule `test-elapsed-upper-bound` enforces that rule.
- **Leave the four host-state tests out of this plan.**: The body of #3593 tracks them in #3585, and read_issue(3585) shows that item closed (completed).

## Rejected alternatives

- **Pass `-n auto` to the pytest command that the test row builds.**: The addopts of `pyproject.toml` already give the full suite `-n logical --dist worksteal`, and the 6m 53s run of the issue used that command, so the option cuts no time.
- **Fail the local gate when the pytest step passes 300 s.**: `docs/TESTING.md` states that no test bounds elapsed wall-clock time from above, and the gate already warns with the step's time and the slowest tests.
- **Cut the suite's constant work until it fits a shared host.**: `docs/TESTING.md` records 355 s on a fast runner and 528 s on a slow one, so no cut of constant work holds the bound on every host, and the project shards the CI row instead.
- **Skip the tests that fail on the agent host.**: #3585 delivers the host-state isolation, and a skip hides the defect on the hosts that show it.
