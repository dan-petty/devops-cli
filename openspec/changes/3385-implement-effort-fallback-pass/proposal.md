# Proposal

## Why

Issue #3385 reports that the implement job takes only low-effort items. The default filter of the job names `effort=low`, so a Ready or Planned item of medium effort waits, even when the job has no low-effort item to take. The Ready backlog holds many medium-effort items, so the service uses less of its implement capacity than it can.

## What Changes

- The default filter of the implement job names `status=ready` and `status=planned`. It no longer names `effort=low`.
- The setting `roadmap.implement.effort` holds the ordered effort values of the job. Its default is `low` and then `medium`. A value that is no effort value, or a value that the list holds twice, is refused, and the refusal names the value.
- The job runs one pass for each effort value, in the order of the setting. The first pass that takes an item supplies the run. A high-effort item stays out of the default set.
- An explicit `--filter effort=` names one pass and replaces the set. The setting does not apply to that run.
- The run report names the effort pass, and it names the fallback when the pass is not the first value of the set. `devops roadmap explain` names the effort set and says whether the fallback pass applies to the item.
- The example ConfigMap holds the setting with its default. `docs/roadmap/implement.md` gives the new default filter and the set.
- The change deletes the `effort=low` entry of `DEFAULT_IMPLEMENT_FILTERS` and the assertion of the test that names it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The default filter, the plan listing, the effort passes, the effort set setting and the run report that names the pass.
- `roadmap-explain`: The implement verdict names the effort set and whether the fallback pass applies.

## Impact

- Code: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/errors.py`.
- Manifests: `k8s/devops/configmap.example.yaml`.
- Documents: `docs/roadmap/implement.md`, and the generated documents that `devops docs generate --sync-readme` writes for the new setting.
- Tests: `tests/roadmap/test_roadmap_implement_selection.py`, `tests/roadmap/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_explain.py`.

## Feasibility

The premise holds at `origin/main` commit `d254410c`. The check read the source with `git show origin/main:<path>`. Line 106 of `src/devops_cli/roadmap/implement.py` sets `DEFAULT_IMPLEMENT_FILTERS` to a tuple that ends with `effort=low`. The function `plan_implement` walks the named items once, with `walk_named`. The function `walk_named` in `src/devops_cli/roadmap/stage.py` judges the items in the order of `_open_items`, which sorts by priority first. One walk over `effort=low` and `effort=medium` would therefore take a higher-priority medium item before a lower-priority low item. That is why the change runs one pass for each effort value. The explain text that the issue quotes is the message `item_left_filter` in `src/devops_cli/lang/en/messages.py`.

Issue #3385 is newer than the archived change `2906-wide-stage-and-implement-filters`, which kept medium items Staged for a person. This change reverses that choice on purpose, as the issue asks. The owner confirms the reversal (see the follow-up in `tasks.md`).

## Existing Tool Considered

No open, maintained tool or library covers the selection of roadmap items by effort. The need is internal. The implement job selects items from the roadmap store of this repository, with the job's own filters, passes and limit. The change therefore builds the passes in the repository's own code. It reuses `walk_named`, `named_items`, `StageFilter`, the pydantic settings model, and `CONST_ROADMAP_SIZE_OPTIONS` for the valid effort values. It adds no dependency.

The written cost of this build is:

- about 1,500 tokens to write the passes, the setting, the explain line and the tests;
- about 500 tokens for each later fix;
- about half a day of elapsed time.

The change deletes the `effort=low` entry of `DEFAULT_IMPLEMENT_FILTERS` and the assertion that names the old tuple in `tests/roadmap/test_roadmap_implement_selection.py`.

## Fit

The change fits one pull request. The pull request closes issue #3385.
