# Proposal

## Why

Issue #2949: if the check of one item fails, the alternatives row writes the other checks and then fails. After 3 failed rounds in a row the Service suspends the row until its input changes. On 2026-10-30 one item (a `UnexpectedModelBehavior` stop on #1127) did this to the whole repository. The failed item has no record, so the next round takes it again among the first items, and the row can meet the same failure.

The change records the failed check in the item's job record and lets the round succeed. A later round takes the item again after `roadmap.alternatives.retry_days` (3 by default). The row fails, and counts toward the suspension, only when the round tried at least one item and checked none.

## What Changes

- A failed check of one item (a failed model call, a stopped run or a refused reply) is recorded in the item's job record with two new keys: `alternatives.failed_at` (the time) and `alternatives.failed_error` (the class of the error). The item is the record itself. A written check clears both keys.
- `select_items` leaves out an item whose `alternatives.failed_at` is less than `roadmap.alternatives.retry_days` days old. `--item` still checks the item it names.
- The new setting `roadmap.alternatives.retry_days` is an integer of at least 1, with default 3.
- `raise_for_failed_checks` raises only when the plan holds failures and no check. The Service row and the command `devops roadmap alternatives` both call it, so both change together. A round that selects no item does not fail.
- The reason of a stopped run adds the bounded `message` that `InvestigationStopped` already holds (#2562, #2922), so the plan report, the error and the log name the cause.
- The documents that state the old behavior name the new one.
- The change fits one pull request. It has three task groups: the retry delay, the failure record, and the rule that fails the row.
- The change has consumer-observable behavior (a command exit code, a setting, the row), so it carries a spec delta. It modifies four requirements of `roadmap-alternatives` and adds two. Each modified requirement states the old rule "fail the round when the check of any item failed", so the base spec would contradict the change if it were only added to.
- Code the change deletes: none. The one rule "any failure fails the round" in `raise_for_failed_checks` is replaced in place.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: the selection leaves out a recently failed item; a failed check is recorded and tried again later; the retry delay is a setting; a round fails only when it checked no item.

## Impact

- Code: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/roadmap/run.py` (the docstring of the alternatives row only).
- Tests: `tests/roadmap/test_roadmap_alternatives.py` (the file that holds every test of the module; four of its tests pin the old behavior and change).
- Documents: `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, and the generated `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `docs/MCP_TOOLS.md`, `docs/CONFIGURATION.md`, `docs/ERRORS.md`.
- Existing code to keep and reuse: `CheckFailure`, `plan_alternatives`, `apply_alternatives` and `raise_for_failed_checks` in `src/devops_cli/roadmap/alternatives.py`; `AlternativesRecordKey` and `RoadmapStore.set_marks` in `src/devops_cli/roadmap/store.py`; `InvestigationStopped` in `src/devops_cli/roadmap/refine_investigation.py`; `DEFAULT_SERVICE_MAX_FAILED_ROUNDS` and the ledger of failed rounds in `src/devops_cli/roadmap/run.py`, which stay as they are. The dry run already lists one `set_marks` write for each item (`alternatives_requests` in `src/devops_cli/roadmap/request_plan.py`), so it needs no change; `tests/roadmap/test_roadmap_dry_runs.py` keeps passing.
- Other plans: the plan of #2946 also edits `src/devops_cli/roadmap/alternatives.py` and adds requirements to the same capability. It modifies none of the requirements that this change modifies, so the two plans do not conflict on specs. The later one to merge may need a rebase of the code.

## Acceptance

- A test with one failing item and four good items ends with a successful round and a record for the failing item: group 2 writes the record, and group 3 makes the round succeed.
- A round in which every item fails still fails: group 3.
- The failed item is tried again after the set time, not before: group 1 leaves the item out of the selection, and group 2 writes the time that group 1 reads. The test of group 2 runs both rounds.
- `uv run devops ci` passes: the last task of group 3 runs it, and the required checks of the pull request run it again.
- The stop reason uses the readable cause (the second bullet of "What should happen"): group 2. The tool-call retry reasons of #2875 and the provider text of #2922 are already in `InvestigationStopped.message`, so the change only adds that message to the reason.

## Feasibility

All commands ran on 2026-11-01 in a worktree at `origin/main` (4734035c).

- The mechanism is as the issue says. `git grep -n "raise_for_failed_checks" -- src` prints `src/devops_cli/roadmap/alternatives.py` line 783 (the function), `src/devops_cli/roadmap/run.py` line 608 (inside `_run_alternatives_adapter`, line 598) and `src/devops_cli/commands/roadmap.py` line 345 (the command). The function raises `RoadmapAlternativesError` when `plan.failures` is not empty, whatever `plan.checks` holds.
- The old behavior is pinned by tests. `uv run devops ci test tests/roadmap/test_roadmap_alternatives.py -k "fails_the_row or skips_its_item"` prints `6 passed`. These tests assert that the row raises after a partial failure, so they change with this plan.
- The item is not skipped for a time today. `git grep -n 'alternatives\.failed\|ALTERNATIVES_RETRY' -- src` prints nothing. `AlternativesRecordKey` (`src/devops_cli/roadmap/store.py` line 165) holds `CHECKED_AT`, `BODY_HASH`, `VERDICT` and `TOOL`. A failed item has no `checked_at`, so `select_items` (`src/devops_cli/roadmap/alternatives.py` line 461) puts it among the first items of the next round.
- The collection of the failures exists. `_check_one` (`src/devops_cli/roadmap/alternatives.py` line 677) returns a `CheckFailure` for `AIClientError`, for an `InvestigationStopped` and (through `validate_reply`) for a refused reply. `UnexpectedModelBehavior` is not raised to the row: `investigate` (`src/devops_cli/roadmap/refine_investigation.py` line 263) returns it as `InvestigationStopped`. So the change records these values and adds no `try` block and no second failure type.
- Rejected credentials are not an item failure. `AICredentialsError` leaves `plan_alternatives` at the first item and writes nothing; the change keeps this. A check that is off (no Firecrawl key, or a private repository) sets `off_reason`, holds no failure, and does not fail the row today. The change keeps this too, so "no search key" in the issue is already a round that does not fail.
- The first draft of this plan named a file `rows` in the roadmap package. No such file exists: `git ls-files src/devops_cli/roadmap | grep -c rows` prints `0`. The row is `_run_alternatives_adapter` in `src/devops_cli/roadmap/run.py`. The tests are in `tests/roadmap/test_roadmap_alternatives.py`, the only file for the module (`git ls-files tests | grep -i altern`).
- The 3-round suspension is the ledger in `src/devops_cli/roadmap/run.py` with `DEFAULT_SERVICE_MAX_FAILED_ROUNDS = 3` (`src/devops_cli/config/defaults.py` line 879). It counts a round that raises. The change needs no change there.
- The base spec says the opposite of the change in four places: `openspec/specs/roadmap-alternatives/spec.md` requires that the run "fail with an error that names each skipped item" and that the row "SHALL fail the round ... when the check of any item failed". The delta therefore uses MODIFIED for these.
- Nothing newer did or removed the work. `git log -1 --format='%h %ad' --date=short -- src/devops_cli/roadmap/alternatives.py` prints `c4623188 2026-10-29` (the commit that added the Service row), so no later commit changed the failure handling. The open issues #2944, #2946, #2947, #2950 and #2951 change the comment, the search rule, the first-pass limit, a gauge and the refine gate; none of them changes `raise_for_failed_checks`.
- The issue's own evidence (the failed rounds of 2026-10-30) is a log record of the Service. It is not checked again here; the code path above reproduces it.

## Existing Tool Considered

No open, maintained tool covers this need. The row, its job record and its ledger are the project's own. The change reuses `CheckFailure`, the job record (`set_marks`) and `InvestigationStopped`, and it adds no new failure type, no store and no scheduler. The written cost is about 3 task groups: the tokens to write about 120 lines of code and about 200 lines of test, and the tokens to keep them, plus the elapsed time to pass `uv run devops ci`. The delay logic is a date compare of the kind that `_is_due` already holds, so a library would add more than it removes.
