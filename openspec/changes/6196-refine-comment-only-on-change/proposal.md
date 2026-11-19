# Proposal: #6196

## Why

#6196 reports that refine writes the same facts in two places, and that it posts the same comment again. The comment of a round (`step_comment`) lists the open questions, the split, the blockers and the watched files, which the body section of refine (`render_proposal_section`) also holds. Each comment also names the checked-at commit and the Status. The owner-question frame repeats the first open question. The repeat guard of the store reads only the trailing run of refine's comments, so a reply of a person lets the same comment post again. Owner rule: a job posts no content in a comment that is already in the issue body.

## What Changes

- The body section of refine holds the whole result of the round. It adds `### Watched files` (the block paths, sorted, so another order gives the same section) and `### Moved to new items` (`refine.deferred`). The labels hold the Status, and the `checked-at` line holds the commit.
- A refine comment is one event line: the next step and the parts of the section that hold it. It holds no list, no commit and no Status sentence. The messages `refine_ready_comment`, `refine_step_comment`, `refine_step_comments`, `refine_back_to_new` and `refine_deferred_comment` go. `refine_event_comment`, `refine_event_steps` and `refine_section_place` replace them.
- The refine owner-question frame names the parts of the section in place of the question text. It keeps the options, the recommendation, the evidence and the hidden hash. `OwnerQuestion.render` takes the place text. The frames of stage and implement keep the question text.
- Refine posts a comment only when the next step, the section without its `checked-at` line, or the item that holds the frame differs from the round before, or when the round files deferred parts. A round that posts no comment records `refine.repeated_at`. A round that posts one clears it. Refine records the item that holds the frame as `refine.frame`, so a linked item looks again when that item closes.
- The wait of an item ends only on a reply made at or after the later of refine's last comment and `refine.repeated_at`. An owner answer on another item counts only from that time too. The model still reads each reply since refine's last comment. A stage return still counts from refine's last comment.
- `_wait_text` reads the parts of the section that name a cause (Open questions, Suspected block, Watched files) and the replies of persons, and no longer the comment of refine.
- The repeat guard of the store (`comment_repeat.fingerprint`) keeps the hash of the owner question of a frame. A refine frame no longer holds the question text, so two frames of two questions differ only in that hash, which the guard masked as an identifier.
- The dry run of `devops roadmap refine` names the change of the result as the condition of the comment (`refine_changed`).
- This change alters observable messages and writes of `devops roadmap refine`, so it carries a spec delta. It fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-refine/comments`: what the body section of refine holds, the event comment, the gate on a changed result and the anchor of a wait after a round with no comment.

### Modified Capabilities

- `roadmap-refine/waits`: the section names the watched files, and the wait text comes from the section and the replies.
- `roadmap-refine/deferred-parts`: the section names the new items of the deferred parts.
- `roadmap-refine/alternatives`: the event line of a wait on the alternatives check.
- `roadmap-job-comments`: the repeat guard keeps the question hash of a frame.

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/owner_question.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/comment_repeat.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`.
- Documents: `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/inbox.md`.
- Tests: `tests/roadmap/refine/`, `tests/roadmap/stores/test_comment_repeat.py`, `tests/roadmap/test_owner_question.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_repair.py`, `tests/support/roadmap_refine.py`.
- Live items: the first round of each waiting item after the merge finds a section of the new form, so it posts one event line.

## Feasibility

- `git show origin/main:src/devops_cli/roadmap/refine/refine.py` showed `step_comment`, which formats `refine_step_comments` with `sha=short` and lists each detail, and `_with_block_paths`, which adds the files. It showed `_with_deferrals`, which adds `Moved to new items` to the Ready comment, and `render_proposal_section`, which writes the same questions, split, block and dependencies to the body.
- The issue body and the comments of #6196 hold the live evidence: the comment `Status set to Ready at 4624bc7b3e25 (see proposed design in issue body).` on #6196 repeats the `checked-at` commit of its own section.
- `src/devops_cli/roadmap/stores/comment_repeat.py` reads `takewhile(lambda comment: marker in comment.body, reversed(comments))`, so a reply of a person ends the run and the same text posts again.
- The section hash (`refine.section_hash`) holds the `checked-at` line, so it differs at each new commit. The gate compares the section without that line, and `check_person_edits` keeps the full hash.
- `_question_ends_wait` read the closed frame holder only through the issue number in the link comment, which `_wait_refs` took from the comment text. The new wait text has no such comment, so the record `refine.frame` replaces that path.
- The saved tests of an earlier attempt applied with `git apply --3way` onto origin/main and failed on the base for the expected causes.

## Existing Tool Considered

The alternatives check of #6196 names peter-evans/create-or-update-comment (MIT, maintained): a GitHub Actions step that edits one bot comment in place by a body marker. It runs in a workflow, not in the roadmap job, and it has no gate on a changed result, no round record and no short event line. This change keeps the roadmap code and adds the gate. The written cost is 150000 tokens and 6 hours to build and test, 3000 tokens each year to keep, and 2000 tokens for each defect. It deletes `_with_block_paths`, `_with_notice`, `_with_deferrals` and five message texts.
