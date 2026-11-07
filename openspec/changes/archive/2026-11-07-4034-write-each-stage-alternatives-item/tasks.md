# Tasks

## 1. The stage row writes each item when that item is done

Kind: behavior.

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/refine/refine.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`. Creates: `tests/roadmap/stage/test_roadmap_stage_item_writes.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_item_writes.py`, write the cases: a kill between item 1 and item 2, a stop of the Service in item 3 with the failure of item 2 recorded, the order of the removals, the rejections, the plan, the publish and the moved paths, and a plan that writes nothing
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_item_writes.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage.py`, add the stage writer with the phase order of the design and the optional `writer` of `plan_stage`. Delete the five-phase batch of `apply_stage` and the single call of `_moved_by_item` for a whole plan. In `src/devops_cli/roadmap/run.py` and `src/devops_cli/commands/roadmap.py`, run `--confirm` and the row with the writer, and `--plan` with none
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_item_writes.py` passes
- [x] 1.3 Keep the other stage tests green with the new order
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_apply.py`

## 2. The alternatives row writes each check when that check is done

Kind: behavior.

Reads: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`. Creates: `tests/roadmap/test_roadmap_alternatives_item_writes.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_alternatives_item_writes.py`, write the cases: a kill in item 3 of 5, a rate limit in the write of check 2, and a plan that writes nothing
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_item_writes.py` fails on the base
- [x] 2.2 In `src/devops_cli/roadmap/alternatives.py`, add the alternatives writer and the optional `writer` of `plan_alternatives`, end the round on a rate limit, and delete the batch loop of `apply_alternatives`. In `src/devops_cli/roadmap/run.py` and `src/devops_cli/commands/roadmap.py`, run `--confirm` and the row with the writer, and `--plan` with none
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_item_writes.py` passes
- [x] 2.3 Keep the other alternatives tests green with the new order
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py`

## 3. The documents match the new order

Kind: documents.

Changes: the documents that state "plan all, then write" for the stage and alternatives rows, if any.

- [x] 3.1 Fix each document that says the stage row or the alternatives row writes after it plans all items
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: A stage round SHALL write the result of each item before it plans the next item.
- Group 1: A stop of the Service SHALL end a stage round after it records the failures of the finished items.
- Group 1: A stage round SHALL write the removals and the rejections of unselected items before its first plan call.
- Group 1: A stage plan SHALL write nothing.
- Group 2: An alternatives round SHALL write the check of an item before it checks the next item.
- Group 2: A rate limit SHALL end an alternatives round and keep the written checks.
- Group 2: An alternatives plan SHALL write nothing.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
