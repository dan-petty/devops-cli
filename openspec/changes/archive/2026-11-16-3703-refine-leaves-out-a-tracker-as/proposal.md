# Proposal

## Why

Refine reads a tracker again after each body edit, because it has no tracker rule, while the stage job leaves one out (#3703). The repeat can spend a model call on the parent and post the split comment again, or set the parent to a new Status.

## What Changes

- Add the property `Item.is_tracker` to `src/devops_cli/roadmap/stores/store.py`, true when the item has sub-issues or the label `type/epic`.
- Make `_tracker` in `src/devops_cli/roadmap/stage/stage.py` read `Item.is_tracker`, and remove the import that the inline test leaves unused, so the two jobs share one definition.
- Leave a tracker out as the first check of `_Selection.consider` in `src/devops_cli/roadmap/refine/refine.py`, before the outside-author check, the body-hash comparison and the comment cap, so it gets no model call, no comment and no write.
- Leave out a tracker that `--item` names, in `_select_single_candidate`.
- Add the message `refine_left_tracker` in `src/devops_cli/lang/en/messages.py`, which `devops roadmap explain` prints through `refine_left_out`.
- Keep the registry of the roadmap limit classes unchanged, because the plan adds and removes no `CONST_ROADMAP_` constant.
- Add `tests/roadmap/refine/test_roadmap_refine_tracker.py`, a case in `tests/roadmap/test_roadmap_explain.py`, and the section in `docs/roadmap/refine.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/selection`: The job leaves out a tracker
- `roadmap-refine/selection`: Refine leaves out a tracker, Refine tells the author of an item that the jobs do not trust one time

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/refine.md`
- Tests: `tests/roadmap/stores/test_roadmap_item_tracker.py`, `tests/roadmap/refine/test_roadmap_refine_tracker.py`, `tests/roadmap/test_roadmap_explain.py`

## Feasibility

- The issue cites `src/devops_cli/roadmap/stage.py` and `src/devops_cli/roadmap/refine.py`, and the probes show that both moved: "The path `src/devops_cli/roadmap/stage.py` is no file at the root of the staging commit." and "Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." The rule lives at `src/devops_cli/roadmap/stage/stage.py` and the round at `src/devops_cli/roadmap/refine/refine.py`, and the plan changes those paths.
- `read_file` of `src/devops_cli/roadmap/stage/stage.py` lines 665-682 confirmed the premise of the issue: `src/devops_cli/roadmap/stage/stage.py:672:def _tracker(self, item: Item) -> str | None:`, `src/devops_cli/roadmap/stage/stage.py:675:is_tracker = item.sub_issues > 0 or CONST_ROADMAP_EPIC_LABEL in item.labels` and `src/devops_cli/roadmap/stage/stage.py:676:return MESSAGES.roadmap.stage_left_tracker if is_tracker else None`.
- `search_code` for `CONST_ROADMAP_EPIC_LABEL` gave the staged value of the constant that the plan relies on, `src/devops_cli/config/constants.py:3774:CONST_ROADMAP_EPIC_LABEL: Final[str] = "type/epic"`, its import at `src/devops_cli/roadmap/stage/stage.py:119:CONST_ROADMAP_EPIC_LABEL,`, and one other reader at `src/devops_cli/roadmap/workflow_labels.py:66:CONST_ROADMAP_EPIC_LABEL, LabelColor.RECORD, "Type epic: a tracker; its sub-issues do work"`. Line 675 is the only use in `stage.py`, so group 1 removes the import.
- `read_file` of `tests/roadmap/test_roadmap_limit_classes.py` lines 40-52 showed the registry that every `CONST_ROADMAP_` constant joins: `tests/roadmap/test_roadmap_limit_classes.py:47:("prefix", "CONST_ROADMAP_", "tests/roadmap/test_roadmap_limit_classes.py"),`. The plan adds no constant and removes none, so no row of the table changes; group 1 reads `tests/roadmap/test_roadmap_limit_classes.py` and changes no row of it.
- `references` for `is_tracker` listed only `src/devops_cli/roadmap/stage/stage.py`, so the new property name holds nothing else and that file is in the changes of group 1. `references` for `refine_left_tracker` gave "No line of the commit holds 'refine_left_tracker'.", and `search_code` for it gave no match, so the new message key is free.
- `read_file` of `src/devops_cli/roadmap/stores/store.py` lines 495-550 showed the two inputs and a derived predicate beside them: `src/devops_cli/roadmap/stores/store.py:502:class Item(BaseModel):`, `src/devops_cli/roadmap/stores/store.py:525:labels: tuple[str, ...] = ()`, `src/devops_cli/roadmap/stores/store.py:529:sub_issues: int = 0` and `src/devops_cli/roadmap/stores/store.py:543:def holds_service_stop(self) -> bool:`. The probe line "`Item` defines the field `sub_issues` at src/devops_cli/roadmap/stores/store.py:529" confirms the count.
- `read_file` of `src/devops_cli/roadmap/stores/store.py` lines 38-60 showed the import block that the property joins: `src/devops_cli/roadmap/stores/store.py:45:from devops_cli.config.constants import (` with `CONST_ROADMAP_OWNER_VALUES` first, so `CONST_ROADMAP_EPIC_LABEL` goes before it and no new import line is needed.
- `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 2586-2632 showed the order of the round: `src/devops_cli/roadmap/refine/refine.py:2590:def consider(self, item: Item) -> None:` runs the outside-author check at `src/devops_cli/roadmap/refine/refine.py:2595:outside = _outside_author(item)`, which sets `src/devops_cli/roadmap/refine/refine.py:2601:self.waiting.append(replace(outside, notice=not told))`, then the unchanged-body comparison at `src/devops_cli/roadmap/refine/refine.py:2611:if is_unchanged(item, item.body) and not _needs_second_look(item):`, and takes the item at `src/devops_cli/roadmap/refine/refine.py:2624:self.selected.append(item)`. The tracker check runs before line 2595.
- The explain path is the same selection: `src/devops_cli/roadmap/refine/refine.py:def refine_left_out` judges the item with the rules of `select_candidates` and formats the waiting text, and `src/devops_cli/roadmap/explain.py:def explain_item` puts it in the refine verdict, so `devops roadmap explain` prints the tracker text and writes nothing.
- `read_file` of `src/devops_cli/lang/en/messages.py` lines 2855-2888 showed the map that prints the reason as it is and the key the plan adds beside: `src/devops_cli/lang/en/messages.py:2862:"none": "{details}",` and `src/devops_cli/lang/en/messages.py:2869:refine_held_closed: str = "The issue is closed: refine changes only open items."`.
- The comment and the notice are written by apply, not by the round: `src/devops_cli/roadmap/refine/refine.py:def apply_refine` calls `src/devops_cli/roadmap/refine/refine.py:def _apply_refined` for the body and the comment and `src/devops_cli/roadmap/refine/refine.py:def _apply_waiting` for the notice, and `src/devops_cli/roadmap/refine/refine.py:def _record_waits` skips a wait with no marks. Group 2 therefore runs `plan_refine` and then `apply_refine` before it asserts a comment, and asserts the absence for a tracker through the comment bodies, the unchanged body and the unchanged job record.
- `src/devops_cli/roadmap/refine/refine.py:def _select_single_candidate` is the path of `--item`, so the same waiting entry there leaves a named tracker out.
- `tests/support/roadmap_refine.py:def comment_bodies` gives the comment bodies of an item, and `tests/roadmap/refine/test_roadmap_refine_selection.py` runs `apply_refine` after `plan_refine`, which the new tests follow.
- `plan_refine(store, repo=REPO, source=git_repo)` needs a checkout of the repository, which the `git_repo` fixture of `tests/support/roadmap_refine.py` makes. `apply_refine` and `refine_left_out` need only the store.
- `explain_item` in the new explain case needs a checkout of the repository, which the `job_world` fixture of `tests/roadmap/test_roadmap_explain.py` makes. The `_seed` helper there takes no `sub_issues` keyword yet, so group 3 adds it.
- `scripted_gateway` needs a client of the model service, and `tests/support/roadmap_refine.py` points it at a local fake, so the new tests reach no network.
- The plan introduces no program and no failure class: each verify runs `uv run devops ci test`, which runs `pytest` from the runner image, where `pytest` is an installed runner tool. No pod setting changes, and the settings stay at `readOnlyRootFilesystem: true` and `runAsNonRoot: true`.
- The change adds no guard over a set of members: the tracker test is one predicate over two fields of `Item`, and the plan adds no constant, so no row of the registry of `tests/roadmap/test_roadmap_limit_classes.py` changes.
- not checked: the read of `sub_issues_summary.total` into `Item.sub_issues` in `src/devops_cli/roadmap/stores/github_store.py`, and the declaration of `type/epic` in `.github/labels.yml`. The plan reads only the staged field and the staged constant.

## Existing Tool Considered

No open, maintained library covers a filter inside two jobs of this repository, and the rule already exists in `_tracker`. Building the shared property, its message and its tests costs about 100k tokens and 30 minutes.

## Dependencies

- PR #5786 changes `src/devops_cli/lang/en/messages.py`, where this change adds the `refine_left_tracker` key.
- PR #5834 changes `src/devops_cli/lang/en/messages.py` and `src/devops_cli/roadmap/stage/stage.py`, the two files that group 1 edits.
- PR #5868 changes `src/devops_cli/lang/en/messages.py`, where this change adds one key.
- PR #5878 changes `src/devops_cli/roadmap/refine/refine.py` and `src/devops_cli/roadmap/stage/stage.py`, which groups 1 and 2 edit.
- PR #5883 changes `src/devops_cli/roadmap/stage/stage.py`, which group 1 edits.
- PR #5898 changes `src/devops_cli/lang/en/messages.py`, where this change adds one key.
