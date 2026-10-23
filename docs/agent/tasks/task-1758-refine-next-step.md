# Task: Refine gives every item it cannot ready a next step instead of skipping it as unchanged (#1758)

**Issue**: [#1758](https://github.com/dan-petty/devops-cli/issues/1758)
**Scope**: type/bug, scope/roadmap
**Feasibility**: Checked on main (a752a14a). `select_candidates` in `src/devops_cli/roadmap/refine.py` skipped every item whose body and section hashes matched its job record as "unchanged", and the `--item` path skipped an unchanged item with "body and section unchanged" and a Ready item with "status Ready is not New". This matches the owner's runs on 2026-10-23 for #1758 and #691. Both store adapters already read an issue's comments (`comments_on`), and the GitHub adapter keeps the job record keys it does not know on each write (`_JOB_RECORD_KEYS` in `github_store.py`), so two new record keys need no migration. A scratch run of `_extract_heading_bullets` over a section that `render_proposal_section` wrote returned `['None.']`: `validate_proposal` read refine's own "Key questions" heading as the person's, so every second refine of an item found an open question. No open tool covers this job's own selection rules, so the change extends the job.

## Description

An item that refine does not set to Ready now gets a next step. The step goes into its job record and into one comment, and the report groups the items by step.

- **`NextStep`** (`src/devops_cli/roadmap/refine.py`) names what an item waits on: `ready`, `person` (open questions, a suspected block, or a proposal with no checkable criterion), `split` (the proposed items for a person to make), `blocked` (open dependencies), `edit` (refine cannot write a design for the body: too big, two replies that never validated, or a person edited refine's section) and `none` (an item `--item` names that is closed, In Progress, Done or Blocked).
- **One comment for each refined item.** `step_comment` writes the Ready notice or the next step with its points: the questions, the numbered split or the blockers. A Ready item that goes back to New gets the Status change in the same comment. Every refine comment starts with `CONST_ROADMAP_REFINE_COMMENT_MARKER`. The points are the model's text, so they pass through `sanitize_text` and stay on one line each.
- **The record.** `apply_refine` writes `refine.next_step` and `refine.blocked_by` (`RefineRecordKey.NEXT_STEP`, `RefineRecordKey.BLOCKED_BY`) with the hashes. An item too big to refine, and an item whose replies settle it, record `edit`.
- **When refine looks again.** An unchanged item waits while its step holds. A comment after refine's last comment ends a `person`, `split` or `blocked` wait, so a reply works the same as a body edit. The close of every item that blocks it ends a `blocked` wait, which `store.item` reads. An `edit` wait ends only with a body edit. An item that refine set Ready and a person set back to New waits for that person's comment, such as the one `devops roadmap return` posts. An unchanged item whose record holds no step is refined again, so the items that earlier rounds left New get a step. Each waiting item costs one comment read and no model call.
- **The replies reach the model.** The proposal request carries `replies`: the comments since refine's last comment, or every comment when refine left none. It keeps the newest `CONST_ROADMAP_REFINE_MAX_REPLIES` and cuts each to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS`. `roadmap_refine_proposal.md` tells the model to give an answer from a reply as a `decision`.
- **`--item` refines the item it names** when it is open and New or Ready, also when nothing changed since its last round. An item that is closed, In Progress, Done or Blocked (`CONST_ROADMAP_REFINE_HELD_STATUSES`) is reported with nothing to do and the reason.
- **The report** (`render_refine_plan`) lists each item under its step's heading: Refined to Ready, Waiting on a person, Split proposed, Blocked by open items, Waiting on a body edit, Nothing to do. It then lists the failed items. No item is listed without a step.
- **The person's questions only.** `validate_proposal` reads the key questions and owner decisions from the body outside refine's section, so a second refine does not ask the section's own questions or its "None." again.
- The dry-run plan (`refine_requests`) lists the comment read of each item and the read of each blocker. The help text and the generated command documents describe the next steps.

## Acceptance Criteria

- [x] With the in-memory roadmap store, items that refine leaves New get the `person`, `split` and `blocked` steps, and the next round leaves each one waiting with no model call (`tests/test_roadmap_refine.py::test_each_item_refine_leaves_new_waits_on_its_next_step_with_no_model_call`).
- [x] Each such item gets one comment with the marker and its points, and its record holds the step, `refine.needs_split` and the blockers (`test_an_item_refine_cannot_ready_gets_one_comment_and_a_record_of_its_next_step`). The model's text in the comment is sanitized, one line for each point (`test_the_next_step_comment_holds_the_models_text_sanitized_and_one_line_for_each_point`).
- [x] A person's reply makes the item eligible again, and the model reads the reply (`test_a_persons_reply_makes_an_item_that_waits_on_them_eligible_and_reaches_the_model`). The close of its blocking item makes a blocked item eligible again (`test_closing_the_item_that_blocks_an_item_makes_it_eligible_again`).
- [x] An unchanged item whose record holds `refine.needs_split` and no step is refined again, and its split goes to a person in a comment (`test_an_unchanged_item_whose_record_needs_a_split_but_holds_no_step_gets_its_split_handed_on`).
- [x] An item that a person sets back to New waits for their reason, and their comment makes refine look again (`test_an_item_a_person_sets_back_to_new_waits_for_their_reason_and_is_refined_after_it`).
- [x] `--item` refines an unchanged New item and a Ready item (`test_an_item_named_with_item_is_refined_though_nothing_changed_since_its_last_round`). It reports a closed, In Progress, Done or Blocked item with nothing to do and calls no model (`test_an_item_named_with_item_that_refine_never_changes_has_nothing_to_do`, `test_an_item_named_with_item_that_is_closed_has_nothing_to_do`).
- [x] The report groups every item by its next step, and a snapshot holds its text (`test_the_report_groups_every_item_under_its_next_step`).
- [x] The questions and the "None." of refine's own section open no question on the next refine (`test_the_key_questions_of_refines_own_section_are_never_asked_again`).
- [x] An item that refine cannot write a design for waits on a body edit, and a comment does not end that wait (`test_an_item_whose_refined_body_is_too_big_is_selected_once_and_its_body_never_written`).
- [x] The refine dry run lists each item's comment read and each blocker's read (`tests/test_roadmap_dry_runs.py::test_a_refine_plan_reads_each_items_comments_and_each_open_blocker`).
- Pending a person: run `uv run devops roadmap refine --repo dan-petty/devops-cli --item 1758`. The report lists #1758 under a next step heading after one model call, and it does not skip the item.
- Pending a person: run `uv run devops roadmap refine --repo dan-petty/devops-cli --confirm`. Each item the round leaves New gets one comment with its next step. Run the same command again with no edit in between: the report lists those items under their next step headings and sends no model request for them.

## Decisions and deviations

- **A split goes to a person.** Refine posts the proposed items for a person to make. It files no child items through intake, because intake's own change (#1755) is open on another branch.
- **A reply is any comment after refine's last comment.** The store reads comment bodies only, and refine posts at most one comment for each item in each round, so the marker on refine's comments is enough.
- **One comment read for each waiting item.** The issue listing gives no comment count to the Item, so the round reads the comments of each item that waits. It reads no body and calls no model for such an item.

## Deliverables

- [x] `src/devops_cli/roadmap/refine.py`: `NextStep`, `WaitingItem`, `next_step_of`, `step_comment`, `replies_since_refine`, the selection waits, `--item`, the records, the replies in the request, the report, `validate_proposal` and the module docstring.
- [x] `src/devops_cli/roadmap/store.py`: `RefineRecordKey.NEXT_STEP` and `RefineRecordKey.BLOCKED_BY`.
- [x] `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md` and `src/devops_cli/roadmap/request_plan.py`.
- [x] `tests/test_roadmap_refine.py`, `tests/__snapshots__/test_roadmap_refine.ambr` and `tests/test_roadmap_dry_runs.py`.
- [x] The generated command documents, and the lines of `task-744`, `task-1515` and `task-1539` that this change made wrong.
- Not in this change: the comment of 2026-10-20 also asks that a full backlog of Ready items does not stop the second pass, which counts `refine_ready_target` across the open milestones and the whole backlog. That rule is #1515's: moved to #2004.
- Not in this change: refine looks at a blocked item again when the code it cites changes: moved to #2005.
