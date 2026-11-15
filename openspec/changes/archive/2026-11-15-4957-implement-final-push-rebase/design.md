# Design

## Decisions
- In `ImplementRun._push`, fetch and rebase immediately after the scoped checks by calling `tip = self._current_tip(in_step=False)`.
- Pass `tip` to `_publish(tip)` or `_push_with_lease(tip)` and record `self.published_sha = tip`.
- On a rebase conflict, `_rebase` aborts and raises `_StopError` with `push=False` and `failure_class=FailureClass.CONFLICT`. The job stops and pushes nothing.

## Rejected alternatives
- Push `self._head()` without fetching after scoped checks: Rejected because the default branch can move while scoped checks run, leaving the pushed head behind.
- Repeat scoped checks after the rebase: Rejected because pull request checks in CI validate the merge with the default branch.
