# Tasks

## 1. Add the shared tracker test to Item

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stores/test_roadmap_item_tracker.py` (new).

- [ ] 1.1 `test_is_tracker_is_true_for_sub_issues_and_for_the_epic_label` in `tests/roadmap/stores/test_roadmap_item_tracker.py` fails first on the missing `Item.is_tracker`; a second case asserts that `_tracker` of `src/devops_cli/roadmap/stage/stage.py` gives `MESSAGES.roadmap.stage_left_tracker` for a tracker and None for a plain item
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_item_tracker.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/stores/store.py`, add `CONST_ROADMAP_EPIC_LABEL` to the import block at line 45, first in that alphabetical list, and add the property `is_tracker` to `Item` after `holds_service_stop`: it returns true when `sub_issues` is above zero or the labels hold `CONST_ROADMAP_EPIC_LABEL`. Let `_tracker` in `src/devops_cli/roadmap/stage/stage.py` return `MESSAGES.roadmap.stage_left_tracker` when `item.is_tracker` is true and None otherwise, and remove `CONST_ROADMAP_EPIC_LABEL` from the import block at line 119, where it has no other use, so `ruff` reports no unused import. Read `tests/roadmap/stage/test_roadmap_stage_selection.py` and leave its tracker case as it is: it pins the stage answer, which does not change. Read `tests/roadmap/test_roadmap_limit_classes.py` too: its registry at `tests/roadmap/test_roadmap_limit_classes.py:47` names the `CONST_ROADMAP_` prefix and the file itself, and this group adds no constant and removes none, so the table keeps every row and the registry test passes with no edit to that path
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_item_tracker.py` passes

## 2. Leave a tracker out of a refine round

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/explain.py`, `tests/roadmap/refine/test_roadmap_refine_selection.py`, `tests/support/roadmap_refine.py`, `docs/roadmap/refine.md`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `docs/roadmap/refine.md`, `tests/roadmap/refine/test_roadmap_refine_tracker.py` (new).

- [ ] 2.1 Write `tests/roadmap/refine/test_roadmap_refine_tracker.py` first: `test_a_round_leaves_out_an_item_with_sub_issues_and_an_item_with_the_epic_label`, `test_a_named_tracker_is_left_out`, `test_a_tracker_of_an_untrusted_author_gets_no_notice_comment`, `test_refine_left_out_gives_the_tracker_text` and `test_a_plain_item_is_still_refined` fail on the missing rule; each runs `plan_refine` and then `apply_refine`, because `_apply_refined` and `_apply_waiting` of `src/devops_cli/roadmap/refine/refine.py` write the body, the comment and the notice
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_tracker.py` fails on the base
- [ ] 2.2 Add the key `refine_left_tracker` to `src/devops_cli/lang/en/messages.py` beside `refine_held_closed`: an item is a tracker when it has sub-issues or the label type/epic, and its sub-issues deliver it, so refine leaves it alone. In `src/devops_cli/roadmap/refine/refine.py`, add the first check of `_Selection.consider`: when `item.is_tracker` is true, append `WaitingItem(item, NextStep.NONE, (MESSAGES.roadmap.refine_left_tracker,))` and return, before the outside-author check, so a tracker gets no notice comment either. Add the same waiting entry to `_select_single_candidate` after the held-status check, so `--item` leaves a tracker out too, and name the rule in the module docstring. The new module seeds a tracker with two sub-issues through `store.seed_issue(..., sub_issues=2)`, a tracker with the label through `seed_item`, a tracker of an untrusted account and a plain item, runs `plan_refine` and then `apply_refine`, and asserts that only the plain item sends a model request, that `comment_bodies` gives no comment for each tracker, that each tracker keeps its body and its job record, that `refine_left_out` returns the tracker text, and that `--item` on a tracker selects no item and posts no comment
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_tracker.py` passes
- [ ] 2.3 Edit `docs/roadmap/refine.md` to add the section `## Items that are trackers`: an item with sub-issues or the label `type/epic` waits with the text of `refine_left_tracker`, the round makes no model call and writes nothing for it, and a person closes the parent, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 3. Test the explain reason for a tracker

Kind: other. Reads: `tests/roadmap/test_roadmap_explain.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`. Changes: `tests/roadmap/test_roadmap_explain.py`.

- [ ] 3.1 In `tests/roadmap/test_roadmap_explain.py`, add the keyword `sub_issues: int = 0` to `_seed` and pass it to `world.store.seed_issue`, then add `test_a_new_tracker_gets_the_refine_tracker_text`: seed an open New item with two sub-issues, call `_explain`, and assert that `explained.refine` is `JobVerdict(False, TEXTS.refine_left_tracker)` and that the store wrote no body, comment or field for the item
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_explain.py` passes

## Criteria

- Group 2: An item with sub-issues or the label `type/epic` makes no model call in refine and gets no refine comment.
- Group 1: The two jobs use one definition of a tracker.
- Group 3: `devops roadmap explain` gives the reason for a tracker that refine leaves out.
- Group 2: A test covers an item with sub-issues and an item with the label.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
