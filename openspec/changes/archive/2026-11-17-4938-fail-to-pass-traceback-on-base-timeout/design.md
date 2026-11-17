# Design

## Decisions

### Catch the timeout once in `_run_pytest_replay`

That function runs the base, plain-base and head replays. A catch there covers each replay with
one change and reuses the existing could-not-run report. A catch only in `replay_on_base` would
leave the head and plain-base replays uncaught.

### Carry the limit in `ReplayCouldNotRun`

A `timeout_seconds` field separates a timeout from a pytest exit status. The report branches on
it, names the limit and the test files, and prints no status that pytest did not return. Reusing
exit status 124 would print a status that pytest never returned, and putting the message in
`output_tail` would mix a structured reason with raw output.

### Keep the documented exit status

A timed-out replay makes the report unsatisfied, so the command exits 1, as it does for an
interrupted pytest. A new status would add a contract that callers do not expect.

### Handle the head and plain-base replays

The head replay keeps a `ReplayCouldNotRun` with its timeout field, so the head report names the
limit too. A plain-base timeout becomes the report's base could-not-run result. A gate-row timeout
returns the same model and prints its own line.

### No new limit and no parallel base run

The process runner's existing 1,800 second limit is named in the report. A CLI option or an
environment variable would hide the limit. Adding xdist to the base run changes the replay and is
separate work.

## Rejected alternatives

- **Let `TimeoutExpired` propagate:** it prints the traceback that the issue reports.
- **Reuse exit status 124:** it reports a pytest status that pytest did not return.
- **Catch only in `replay_on_base`:** the head and plain-base replays keep the traceback.
- **A larger limit:** a loaded host can exceed any fixed limit, and the limit is not the contract.
- **Make the base run parallel:** it changes the test run and does not handle the timeout.
