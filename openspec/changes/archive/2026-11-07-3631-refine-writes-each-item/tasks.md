# Tasks

## 1. Write each item when that item is done

Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_round.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_placeholder.py`. Creates: `tests/roadmap/refine/test_roadmap_refine_round.py`.

- [x] 1.1 In `tests/roadmap/refine/test_roadmap_refine_round.py`, write the cases: a round that stops in item 3 keeps items 1 and 2 and the next round takes item 3, a failed write costs the other items nothing and the round logs its counts, and `plan_refine` with no writer writes nothing
  - Verification: `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_round.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/refine/refine.py`, split `apply_refine` into per-item functions, add `RefineWriter` and the `writer` argument of `plan_refine`, and name the items whose write failed in `raise_for_failed_items`. In `src/devops_cli/roadmap/run.py`, run the round with the writer. Add the log texts to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_round.py` passes
- [x] 1.3 In `tests/roadmap/refine/test_roadmap_refine_placeholder.py`, make the planned-round stub give its failures to the writer
  - Verification: `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_placeholder.py` passes

## Criteria

- Group 1: The refine round SHALL write the result of each item when that item is done, before it takes the next item.
- Group 1: The round SHALL write no item when `plan_refine` runs with no writer.
- Group 1: A write that fails for one item SHALL NOT stop the writes of the other items.
- Group 1: The round SHALL log its start and its end, and the end line SHALL give the counts of items taken, written and failed.

## Workflow follow-up

- The live run of three rollouts in 2 hours needs a release period: #3793.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
