# Proposal

## Why

A stop of the implement job sets `status/blocked` and records `implement.stopped` (#2912). A person or an agent often fixes such an item by hand. `devops pr create` and `devops pr ready` leave a Blocked item Blocked, because `set_delivered_status` in `src/devops_cli/roadmap/pull_status.py` replaces no Blocked Status. The item stays Blocked while its fix pull request is open and in review (#2967).

## What Changes

- `set_delivered_status` replaces `status/blocked` when a job recorded it with a stop on record: the label is Blocked, the Status that a job last recorded is Blocked, and `implement.stopped` holds a step. `devops pr create` then sets In Progress and `devops pr ready` sets In Review.
- A `status/blocked` label that a person set by hand stays, because no job recorded it.
- `Item.holds_service_stop` in `src/devops_cli/roadmap/store.py` holds that rule once. `is_service_stop` in `src/devops_cli/roadmap/stop_clear.py` calls it and adds the state, claim and Job checks, so the two rules cannot drift apart.
- The module docstring of `pull_status.py` and the Item state table in `docs/ROADMAP_WORKFLOW.md` describe the new rule.
- The requirement "A Status moves forward only" of `roadmap-item-labels` changes, because the Status that `devops pr create` and `devops pr ready` write is observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-item-labels`: A Status moves forward only

## Impact

- Code: `src/devops_cli/roadmap/pull_status.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/stop_clear.py`
- Tests: `tests/commands/test_pr_status.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`

## Feasibility

- The premise holds in the code. `_REPLACES` in `src/devops_cli/roadmap/pull_status.py` has no Blocked in the set of either target, so `set_delivered_status` returns None for a Blocked item. The test `test_the_status_moves_forward_and_never_leaves_blocked` in `tests/commands/test_pr_status.py` pins that for both targets.
- The record that the rule reads exists. `store.set_field` records the Status in the job record, and the stop path records `implement.stopped` (`implement_run.py`, `implement_submit.py`). A label that a person set by hand has no job record, so its recorded Status differs from `status/blocked`. `is_service_stop` in `src/devops_cli/roadmap/stop_clear.py` already tells the two apart with this test.
- `status_sync.owns_status` writes only Ready and Planned labels, so a Status of In Progress or In Review that `pr create` and `pr ready` write is not rewritten by the Service. `implement.py` leaves a stopped item with no `implement: retry` comment, so the Service starts no Job over the pull request of the person. The change keeps `implement.stopped` on record.
- The run `uv run devops ci fail-to-pass --base origin/main` shows the new cases fail on the base and pass on the branch.

## Existing Tool Considered

No open, maintained tool covers the need. The rule reads the job record of this repository's own roadmap store. The change reuses the rule of `is_service_stop`, moves it to one method of `Item` and builds no new parser. It deletes the copy of that rule in `is_service_stop`. The written cost is about 3k tokens to build, keep and fix, and 30 minutes.

## Dependencies

None.
