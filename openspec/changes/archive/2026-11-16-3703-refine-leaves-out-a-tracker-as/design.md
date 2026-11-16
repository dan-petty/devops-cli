# Design

## Decisions

- **Put the one tracker test on the model as the property `Item.is_tracker`.**: `Item` holds `labels` and `sub_issues`, both jobs import it, and it already carries a derived predicate in `holds_service_stop`, so one property gives one definition with no new module and no import cycle.
- **Run the tracker check as the first check of `_Selection.consider`, before the outside-author check.**: An item that the selection never takes reaches neither the notice, nor the body-hash comparison, nor `refine_one_item`, so it gets no model call, no comment and no write, and `refine_left_out` runs the same check for `devops roadmap explain`.
- **Leave out a tracker that `--item` names, in `_select_single_candidate`.**: The stage job keeps its tracker check under `--item` too, and the issue states the exclusion with no exception, so the two jobs agree.
- **Add the message key `refine_left_tracker` instead of reusing `stage_left_tracker`.**: The text of `stage_left_tracker` names the stage job and says the item gets no plan, which is the wrong reason for a round that only reads the item.
- **Give the reason through the selection and `refine_left_out`, with no record write.**: `devops roadmap explain` recomputes the verdict from the same function a round uses and writes nothing, so the tracker keeps its body, its marks and its Status.
- **Test the sub-issue count only, with no filter on the state of the sub-issues.**: `_tracker` tests `sub_issues > 0` with no state filter, and one shared test cannot give two answers for one item.
- **Run `plan_refine` and then `apply_refine` in the new refine tests.**: The comment and the outside-author notice are written by `_apply_refined` and `_apply_waiting` inside `apply_refine`, so a test that runs only `plan_refine` observes no comment and proves nothing about the absence of one.
- **Modify the base requirement that gives the outside-author notice so that a tracker gets none.**: The tracker check runs first, and the notice tells the author to run `devops roadmap refine --item <number>`, which now leaves a tracker out, so the notice would ask for a round that cannot happen.
- **Remove `CONST_ROADMAP_EPIC_LABEL` from the import block of `src/devops_cli/roadmap/stage/stage.py` in the same group.**: Line 675 is the only use of the constant in that file, so the import becomes unused and `ruff check` reports F401 in the Static Analysis row.
- **Read `tests/roadmap/test_roadmap_limit_classes.py` in group 1 and change no row of its registry.**: `tests/roadmap/test_roadmap_limit_classes.py:47:("prefix", "CONST_ROADMAP_", "tests/roadmap/test_roadmap_limit_classes.py"),` holds the registry of every `CONST_ROADMAP_` constant, and the plan adds none and removes none, so the test that compares the registry with the code passes with no edit.
- **Keep the existing stage test as the pin of the stage side and add a test module for the property and the refine rule.**: `tests/roadmap/stage/test_roadmap_stage_selection.py:def test_a_tracker_is_left_out_under_the_wide_default_filter` already pins the stage answer for the label, the sub-issues and both, so only the new behavior needs a test.

## Rejected alternatives

- **A function in `stage.py` that the refine job imports.**: The refine module already imports the store and the messages, and importing the stage job would couple the two rows of the Service.
- **A new module `src/devops_cli/roadmap/tracker.py` for the one predicate.**: The predicate reads only two fields of `Item`, which sits in `src/devops_cli/roadmap/stores/store.py`, so a module would add an import for no state of its own.
- **A copy of the tracker check inside the refine selection.**: Two copies drift, and the issue asks for one definition that both jobs share.
- **Run the tracker check after the body-hash comparison in `consider`.**: `src/devops_cli/roadmap/refine/refine.py:2611:if is_unchanged(item, item.body) and not _needs_second_look(item):` lets the parent through once its body edit moves the hash, which is the cost the issue removes.
- **Run the tracker check in `refine_one_item` only.**: `refine_left_out` reads the selection and not the round, so explain would give no reason and the item would still take a place under the limit.
- **Reuse `stage_left_tracker` as the refine reason.**: The text names the stage job and the plan, so the reason would not say what refine does.
- **Keep the outside-author notice for a tracker by running the tracker check after the author check.**: The notice at `src/devops_cli/lang/en/messages.py:2882:refine_outside_notice: str = (` tells the author to run `devops roadmap refine --item {number}`, which this change makes a no-op on a tracker, and the issue states that a tracker gets no refine comment.
- **Assert the comment of the plain item from `plan_refine` alone.**: `src/devops_cli/roadmap/refine/refine.py:def _apply_refined` writes the comment inside `apply_refine`, so `plan_refine` writes no comment and the assertion would pass whatever the code does.
