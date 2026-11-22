# Tasks

## 1. Find a block marker only as an HTML block in body_hash

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/test_roadmap_repair.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/refine/test_roadmap_refine_blocked.py`, `tests/roadmap/refine/test_roadmap_refine_cited_paths.py`, `tests/roadmap/refine/test_roadmap_refine_context.py`, `tests/roadmap/refine/test_roadmap_refine_cycle.py`, `tests/roadmap/refine/test_roadmap_refine_decisions.py`, `tests/roadmap/refine/test_roadmap_refine_deferred.py`, `tests/roadmap/refine/test_roadmap_refine_event_comment.py`, `tests/roadmap/refine/test_roadmap_refine_failure_record.py`, `tests/roadmap/refine/test_roadmap_refine_job_failure.py`, `tests/roadmap/refine/test_roadmap_refine_next_step.py`, `tests/roadmap/refine/test_roadmap_refine_owner_question.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, `tests/roadmap/refine/test_roadmap_refine_proposal.py`, `tests/roadmap/refine/test_roadmap_refine_sanitize.py`, `tests/roadmap/refine/test_roadmap_refine_selection.py`, `tests/roadmap/refine/test_roadmap_refine_waits.py`, `tests/roadmap/stage/test_roadmap_stage_held.py`, `tests/roadmap/stage/test_roadmap_stage_item_writes.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `tests/roadmap/stage/test_roadmap_stage_rejected.py`, `tests/roadmap/steps/test_roadmap_step_review.py`, `tests/roadmap/test_roadmap_explain.py`. Changes: `src/devops_cli/roadmap/body_hash.py`, `tests/roadmap/test_roadmap_body_hash.py` (new), `tests/roadmap/refine/test_roadmap_refine_sanitize.py`.
Adds: `JOB_BLOCK_MARKERS`, `block_marker_spans`, `job_block_bounds`

- [x] 1.1 Write `test_a_quoted_marker_pair_is_no_block` in `tests/roadmap/test_roadmap_body_hash.py` first: it asserts that `extract_section_and_outside` returns a body that quotes the refine markers in code spans as its outside text with no section, that `without_alternatives` keeps a body that quotes the alternatives markers in code spans, and that a real block is still cut; it fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py` fails on the base
- [x] 1.2 Add `JOB_BLOCK_MARKERS`, `block_marker_spans` and `job_block_bounds` to `src/devops_cli/roadmap/body_hash.py`. `block_marker_spans` parses the body with `MarkdownIt("commonmark")`, maps each `html_block` token to its character span with the token's line map, and keeps the span of the marker text where the stripped token content is one of the markers. `job_block_bounds` returns the span from the first start-marker span to the end of the next end-marker span, and None when the body holds no such pair. `extract_section_and_outside` slices on that pair, so a marker in a code span, a code block or a paragraph stays in the person's text
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py` passes

## 2. Share one job block marker set with refine

Kind: other. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`.

- [x] 2.1 Remove `_JOB_BLOCK_MARKERS` from `src/devops_cli/roadmap/refine/refine.py` and import `JOB_BLOCK_MARKERS` from `src/devops_cli/roadmap/body_hash.py`. `_ends_section` keeps its token test and reads the shared set, so the section ending and the block writing use one rule. Move the comment above the set with it
  - Verification: `$ uv run devops ci test tests/roadmap/refine` passes

## 3. Add the alternatives block at the end when the markers are quoted

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/stores/test_roadmap_store_tool_issues.py`, `tests/roadmap/test_roadmap_alternatives_item_writes.py`, `tests/roadmap/test_roadmap_alternatives_job_result.py`, `tests/roadmap/test_roadmap_alternatives_one_write.py`, `tests/roadmap/test_roadmap_alternatives_page_links.py`, `tests/roadmap/test_roadmap_alternatives_project_facts.py`, `tests/roadmap/test_roadmap_alternatives_recheck.py`, `tests/roadmap/test_roadmap_alternatives_reply_fixable.py`, `tests/roadmap/test_roadmap_alternatives_search.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_item_comments.py`, `tests/roadmap/test_roadmap_run_adapter_imports.py`, `tests/roadmap/test_roadmap_run_row_cadence.py`, `tests/roadmap/test_roadmap_trust.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives.py`.

- [x] 3.1 Write `test_the_alternatives_writer_keeps_a_quoted_marker_pair_and_appends_its_block` in `tests/roadmap/test_roadmap_alternatives.py` first, covering the requirement `A marker bounds a block only as an HTML block`: a body that quotes both markers in code spans with the word to between them keeps every character after a write and gets the new block at the end, and a body whose markers are each an HTML block on a line of its own has its block replaced. It fails on the base because the quoted word is replaced
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [x] 3.2 Change `_marker_problem` and `_with_block` in `src/devops_cli/roadmap/alternatives.py` to find the markers with `job_block_bounds` and `block_marker_spans` from `src/devops_cli/roadmap/body_hash.py`. `_marker_problem` names a problem only when an HTML-block marker has no partner. `_with_block` replaces the block that the pair delimits, and adds its block at the end when the body holds no such pair
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py` passes

## 4. Cut the refine block only at an HTML block marker in the stage criteria

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/stage/stage_criteria.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`, `tests/roadmap/implement/test_roadmap_implement_resplit.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_requirements.py`, `tests/roadmap/stage/test_roadmap_stage_split.py`, `tests/roadmap/stage/test_roadmap_stage_text_lines.py`, `tests/roadmap/test_roadmap_plan_read.py`. Changes: `src/devops_cli/roadmap/stage/stage_criteria.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`.

- [x] 4.1 Write `test_a_quoted_marker_pair_keeps_the_criteria_and_gives_no_refine_block` in `tests/roadmap/stage/test_roadmap_stage_criteria.py` first: in a body that quotes both refine markers in code spans, with an acceptance criterion and, under another heading, a bullet that names `src/devops_cli/roadmap/body_hash.py` between them, `acceptance_criteria` returns the criterion, `refine_decisions` returns no decision, and `requirement_lines` returns that path as a requirement line; a body whose markers are each on a line of its own still gives its `Chosen` line. It fails on the base, which cuts the text between the quoted markers
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py` fails on the base
- [x] 4.2 Change `_without_refine_block` and `_refine_block` in `src/devops_cli/roadmap/stage/stage_criteria.py` to call `extract_section_and_outside` from `src/devops_cli/roadmap/body_hash.py` instead of `body.find`. A quoted marker pair stays in the text that the job reads, so `acceptance_criteria` and `requirement_lines` read the text between it, and a start marker with no end marker gives no block. Then run `uv run devops roadmap eval stage --replay` and compare the score before the change with the score after it: the replay calls no model, so the score of the stage job must not move
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py` passes
- [x] 4.3 Write `test_a_start_marker_with_no_end_marker_gives_no_refine_block` in `tests/roadmap/stage/test_roadmap_stage_criteria.py`: a body with a real refine start marker on a line of its own, then a `Chosen` line and an acceptance criterion, and no end marker, gives no decision from `refine_decisions`, and `acceptance_criteria` returns the criterion. It fails on the base, which reads the text after the start marker as the block
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py` passes

## 5. Keep the job block readable after an open block

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/trust.py`, `tests/support/roadmap_refine.py`, `tests/support/roadmap_alternatives.py`. Changes: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py` (new), `tests/roadmap/test_roadmap_alternatives.py`.
Adds: `close_open_block`

- [x] 5.1 Write the tests first, covering the requirements `Refine keeps its section readable after an open block` and `A check keeps its block readable after an open block`. `test_an_open_block_leaves_one_section_and_an_unchanged_item_over_three_rounds` in `tests/roadmap/refine/test_roadmap_refine_block_markers.py` and `test_an_open_block_leaves_one_block_and_an_unchanged_item_over_three_rounds` in `tests/roadmap/test_roadmap_alternatives.py` run three rounds of the real write with a code fence that the model's text leaves open, a code fence that the text of a person leaves open, and an open `<pre>` block of a person: each round leaves one block that a read finds, and the next round reads the item as unchanged. `test_an_open_block_is_closed_so_that_a_block_after_it_is_found` and `test_a_text_with_no_open_block_stays_as_it_is` in `tests/roadmap/test_roadmap_body_hash.py` cover `close_open_block`. `test_a_body_that_quotes_both_markers_keeps_them_and_gets_the_section_at_the_end` covers a refine write to a body that quotes both refine markers, and fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_block_markers.py` fails before the change
- [x] 5.2 Add `close_open_block` to `src/devops_cli/roadmap/body_hash.py`. `render_proposal_section` and the block of the alternatives check close their own text before the end marker. The refine write and `_with_block` close the text before the start marker. Refine records `refine.body_hash` of `new_body`, and the check records `alternatives.body_hash` of the body that it writes
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine tests/roadmap/test_roadmap_alternatives.py` passes

## Criteria

- Group 3: Test first: a body that quotes both markers in code spans and has no block keeps all its text after a write, and the new block is at the end. The test fails on the base.
- Group 1: Test first: `without_alternatives` and `extract_section_and_outside` keep a quoted marker pair and the text between them.
- Group 3: A test: a real block (each marker on its own line) is replaced as before.
- Group 5: Test first: after three rounds with an open code fence or an open `<pre>` block, the body holds one job block and the item reads as unchanged.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
