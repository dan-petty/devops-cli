# Proposal: #4498

## Why

Closes #4498. The stage gate for a stale test path says only "The test path `X` names no file of the staged commit. Correct the path or add the test file." It does not name the file that the plan most likely means. In the stored refused records of the Service, 3 of 3 items with this problem repeated the same wrong path in the second reply, and the item failed. In each one, the staged tree holds exactly one file with the same name in another folder. The path gate already names the files with the same name (`stage_path_same_name`), so the planner can correct a wrong path of `reads` or `changes`, but not a wrong test path.

## What Changes

- The problem of a stale test path ends with the same hint as the problem of a missing path: the text of `stage_path_same_name` that names the files of the staged tree with that name, or the text of `stage_path_no_same_name`.
- One function of `stage_paths.py`, `same_name_hint`, makes this hint. The path gate and the test-path gate both use it, so the two hints cannot drift apart.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: a new requirement says that the problem of a stale test path ends with the same-name hint.

## Impact

- `src/devops_cli/roadmap/stage/stage_paths.py`: the new `same_name_hint`, which `_problem` now calls.
- `src/devops_cli/roadmap/stage/stage_change.py`: `_stale_test_path_problems` adds the hint.
- `src/devops_cli/lang/en/messages.py`: `stage_problem_missing_test_file` gets a `{hint}` placeholder.
- `tests/roadmap/stage/test_roadmap_stage_form.py`: two new tests.
- The stage planner reads the new problem text when it corrects a refused plan. No other reader of the text exists, and no document quotes it.

## Feasibility

I confirmed the premise on 2026-11-11 at origin/main 5f75d256:

- `_stale_test_path_problems` in `src/devops_cli/roadmap/stage/stage_change.py` formats `stage_problem_missing_test_file` with only `{path}`. The template at `src/devops_cli/lang/en/messages.py` has no other placeholder.
- `StagedTree.same_name` in `src/devops_cli/roadmap/stage/stage_paths.py` returns the files of the tree with the file name of a path, sorted and at most `SAME_NAME_MAX`. `_problem` already formats them with `stage_path_same_name`, or uses `stage_path_no_same_name`.
- `git ls-files` finds exactly one file with the name of each wrong path of the issue: `tests/github/test_item_grounding.py`, `tests/support/keyring_isolation.py` and `tests/prometheus/test_k8s_monitoring_alerting.py`.

## Existing Tool Considered

No open tool covers this need: the text is a diagnostic of the stage validator. The change reuses `StagedTree.same_name` and the two hint texts of the path gate, and adds no library. Cost: about 30,000 tokens to build, no upkeep, and about 1 hour of elapsed time.
