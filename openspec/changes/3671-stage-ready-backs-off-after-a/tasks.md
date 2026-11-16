# Tasks

## 1. Grow the watch row's failed-head wait to 60 minutes

Kind: behavior. Reads: `src/devops_cli/roadmap/steps/watch.py`, `tests/roadmap/test_roadmap_watch_row.py`. Changes: `src/devops_cli/roadmap/watch_row.py`, `tests/roadmap/test_roadmap_watch_row.py`.
Adds: `_FAILED_HEAD_WAIT_MINUTES`, `_next_backoff_minutes`

- [ ] 1.1 Write `tests/roadmap/test_roadmap_watch_row.py::test_watch_row_grows_the_failed_head_wait_to_60_minutes` first: a draft plan pull request with a failed check records a wait of 15 minutes and a next read time 15 minutes after the read, then 30, then 60, then 60 at the end of each recorded wait, which the requirement `Watch maintains a ledger with failed head backoff` holds. It fails on the flat 30-minute wait of `src/devops_cli/roadmap/watch_row.py`. The change also updates `tests/roadmap/test_roadmap_watch_row.py::test_watch_row_sends_one_graphql_request_and_backs_off_failed_head`, which asserts the 30-minute first wait
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py` fails on the base
- [ ] 1.2 Add the constant `_FAILED_HEAD_WAIT_MINUTES = (15, 30, 60)` and the pure function `_next_backoff_minutes(recorded: int) -> int` to `src/devops_cli/roadmap/watch_row.py`: it gives 15 for 0, 30 for 15, and 60 for 30 or 60. Add the field `backoff_minutes: int = 0` to `WatchLedgerEntry`. In `_evaluate_pull`, when the verdict is the failed one, take `backoff_minutes` from the entry of the same head when the recorded head equals the head SHA and from zero otherwise, and set `next_read_at` to the read time plus that many minutes; clear both fields for any other verdict. Update the module docstring and the docstring of `watch_round`, which state a 30-minute wait
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_watch_row.py` passes

## 2. State the growing failed-head wait in the watch item

Kind: other. Reads: `docs/CLUSTER.md`. Changes: `docs/CLUSTER.md`.

- [ ] 2.1 In item 18 of the Roadmap service section of `docs/CLUSTER.md` replace the clause `with 30-minute failed-head backoff (#3671)` with the wait that the row records: 15 minutes after the first failed read of a head, then 30 and 60, held at 60, cleared when the head or the base branch moves. State that the row reads the pull request in each round, so a push clears the wait at the next round, and that a running check keeps the 3-minute cadence
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `docs/CLUSTER.md` so item 18 states the 15, 30 and 60-minute failed-head wait and the clear on a moved head
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: a draft with a failed check backs off, and the test holds the interval.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
