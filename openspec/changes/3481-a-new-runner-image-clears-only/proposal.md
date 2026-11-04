# Proposal

## Why

A new runner image clears every stop that the Service set, whatever the cause (#3481). Release commits roll a new image many times a day, so the rule `digest` acts as a loop. The clears put old items first again, and new items wait. In the window of the issue, 22 Jobs followed a digest clear with 0 passes, and they used about half of the input tokens of the stop comments. A new image cannot fix a plan defect, a false premise, a refused tool or a failed test, so these clears only spend tokens.

## What Changes

- A clear by digest runs only for a stop whose class has the action `retry` in `ACTION_BY_CLASS`. A stop with no class on record is not cleared by a digest. A trusted `implement: retry` comment still clears a stop of any class.
- The settings `roadmap.implement.digest_clears_per_class` (default 1) and `roadmap.implement.digest_clears_per_item` (default 3) bound the digest clears of one item. A stop at a limit stays Blocked until `implement: retry`.
- The record key `implement.digest_clears` holds the clears of an item as a JSON list of the class, the digest and the time. A clear does not remove it.
- `priority_order` sorts by priority, then an item with no digest clear before an item with one, then by number.
- The record key `implement.digest_clear_commented_at` holds the time of the last digest-clear comment. A digest clear writes no comment when the last one is less than 24 hours old, and still records the clear.
- The text `Never a loop` leaves the docstring of `stop_clear.py`. No rule reads the files that an image changed.
- `k8s/README.md` step 16, `docs/ROADMAP_WORKFLOW.md`, `docs/ROUTINE_TASKS.md` and the generated settings documents state the rule.
- The change fits one pull request. It depends on #3476 (typed stop classes) only for new classes: the rule reads `ACTION_BY_CLASS`, so a class that #3476 adds with the action `retry` works with no edit here.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: A new runner image clears a stop of a retry class within limits, and the job orders new items before retried items

## Impact

- Code: `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/digest_clears.py` (new), `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/ROUTINE_TASKS.md`, `docs/roadmap/implement.md`, `CONTEXT.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`
- Tests: `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/test_roadmap_digest_clears.py`, `tests/roadmap/test_roadmap_stage_selection.py`

## Feasibility

- Code at `origin/main` (`b3280bad`): `stop_clear.py` rule `digest` calls `_new_digest`, which compares `implement.job_digest` with the digest of the CronJob template and reads no class. The docstring says `Never a loop`.
- `ACTION_BY_CLASS` in `failure.py` maps `provider`, `timeout` and `ci_infra` to `retry`, and `plan_defect` to `amend`, `premise_false` to `return`, `refused_tool` to `wait`, and `test` to `repair`. The issue lists exactly these classes, so the premise holds.
- `implement_run.py` and `implement_submit.py` write `implement.failure` with the class value at each stop, and `stop_clear.py` removes it at a clear. So the class is on record when the rule reads the stop. A clear removes the class, so the clear history needs its own key.
- `priority_order` in `stage.py` returns `(rank, number)`. `named_items` sorts with it, and `implement.py` plans with `named_items`, so one change of the key orders the Service round.
- The Service holds only digests. The runner image has no `image.revision` label, so no map from a digest to commits exists, and the rule reads no image content.
- The first checks are `uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py tests/roadmap/test_roadmap_digest_clears.py tests/roadmap/test_roadmap_stage_selection.py`.

## Existing Tool Considered

Project code covers the need: `_new_digest`, `is_service_stop`, `ACTION_BY_CLASS`, `priority_order` and the record key `implement.failure`. Pydantic (already a dependency) parses and writes the JSON list of the clears, so no hand-written parser is added. No external tool is built, so no build cost applies.

## Dependencies

#3476 (typed stop classes) is built in parallel. This change builds on the classes of `main`, and does not wait for it.
