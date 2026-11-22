# Tasks

## 1. Read each job block marker with one rule

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/repair.py`, `src/devops_cli/roadmap/refine/refine_judge.py`, `src/devops_cli/roadmap/stage/stage_criteria.py`. Changes: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/refine/test_roadmap_refine_dependencies.py`.
Adds: `block_marker_of`, `close_blocks_before_markers`

- [x] 1.1 Write the tests first. The cases `comment-open-above-alternatives` and `fence-open-above-the-refine-block` of `test_a_job_block_marker_ends_the_dependencies_section` in `tests/roadmap/refine/test_roadmap_refine_dependencies.py` give `[4989]`. `test_a_block_that_a_person_leaves_open_ends_at_the_blocks_of_the_jobs` in `tests/roadmap/test_roadmap_body_hash.py` reads the refine section and the alternatives block after an open fence, an open `<pre>` block and an open `<?` block, and gives the text with the close before the first marker. The tests fail on the base
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_dependencies.py` fails on the base
- [x] 1.2 Add `block_marker_of` to `src/devops_cli/roadmap/body_hash.py`, and call it in `_marker_span` and in `_ends_section`. Split a body at the first line of the job blocks at the end of a block that no close ends, and read each part with `block_marker_spans`. Add `close_blocks_before_markers`, cut the body in that form in `extract_section_and_outside`, and parse it in that form in `body_dependencies`. Update the docstrings that the change makes wrong
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_dependencies.py` passes

## 2. Leave one job block after each write

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `tests/support/roadmap_refine.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, `tests/roadmap/test_roadmap_alternatives.py`.

- [x] 2.1 Write the tests first. `test_a_block_that_a_person_opens_above_the_section_leaves_one_section_over_three_rounds` in `tests/roadmap/refine/test_roadmap_refine_block_markers.py` runs three refine rounds after a person opens a code fence or a `<pre>` block above a recorded section: each round leaves one section that a read finds, and the body does not change after the first round. The cases `person-fence-above-the-block`, `person-pre-above-the-block` and `person-fence-above-a-refine-section` of `test_an_open_block_leaves_one_block_and_an_unchanged_item_over_three_rounds` in `tests/roadmap/test_roadmap_alternatives.py` run three checks: each round leaves one block, and the first write adds the close before the first marker. The fence and `<pre>` cases fail on the base
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_block_markers.py tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [x] 2.2 Make `_with_block` in `src/devops_cli/roadmap/alternatives.py` find its block in the body that `close_blocks_before_markers` gives. The refine write keeps the outside text of `extract_section_and_outside`, which holds the close
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_repair.py tests/roadmap/stage/test_roadmap_stage_criteria.py` passes

## 3. Keep each quote of a person in an open block

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/refine/refine.py`. Changes: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, `tests/roadmap/refine/test_roadmap_refine_dependencies.py`.

- [x] 3.1 Write the tests first. `test_a_block_that_a_person_leaves_open_holds_their_quotes_up_to_the_blocks_of_the_jobs` in `tests/roadmap/test_roadmap_body_hash.py` reads an open fence with a quoted block above the block of the job, a lone refine start, a lone alternatives start, a quoted block after the block of the job, text after the block, and a fence in the section. `test_a_marker_that_a_person_quotes_in_an_open_fence_stays_their_text_over_three_rounds` in `tests/roadmap/test_roadmap_alternatives.py` and `test_a_marker_that_a_person_quotes_in_an_open_fence_stays_their_text` in `tests/roadmap/refine/test_roadmap_refine_block_markers.py` run three rounds on a quote. `test_a_write_closes_a_block_that_a_person_opens_above_the_block_of_another_job` runs three refine rounds that write. The round test of a block above the section asserts no model call and no write. The quote cases fail on the head of group 2
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_block_markers.py tests/roadmap/test_roadmap_alternatives.py` fails on the head of group 2
- [x] 3.2 End an open block at the job blocks at its end (`_are_job_blocks`), in `src/devops_cli/roadmap/body_hash.py`. A body has at most one part more than there are job block markers. One job can end two open blocks, so `test_each_job_block_marker_can_end_a_block_that_a_person_leaves_open` reads a body with three open blocks. Update the docstrings that the change makes wrong, also of `_marker_problem`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_repair.py tests/roadmap/stage/test_roadmap_stage_criteria.py` passes

## 4. End a declaration at a marker as a comment

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`. Changes: `src/devops_cli/roadmap/body_hash.py`, `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`.

- [x] 4.1 Write the tests first. `test_a_marker_that_ends_an_open_html_block_of_a_person_bounds_the_block` in `tests/roadmap/test_roadmap_body_hash.py` reads a comment and a `<!DOCTYPE html` declaration that a person leaves open above a job block. `test_an_open_comment_above_the_section_leaves_one_section_over_three_rounds` runs three refine rounds on each. The declaration cases fail on the head of group 3
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_block_markers.py` fails on the head of group 3
- [x] 4.2 Make `block_marker_of` read the end text of each kind of HTML block from `_HTML_BLOCK_CLOSES`, the table of `close_open_block` (`_end_text`), in `src/devops_cli/roadmap/body_hash.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine tests/roadmap/test_roadmap_alternatives.py` passes

## Criteria

- Group 2: Test first: over three rounds of the refine write and of the alternatives writer, a body with an open fence or an open `<pre>` above an existing job block holds one job block after each round. The test fails on the base.
- Group 1: Test first: for the body of case 2, `body_dependencies` gives [4989]. The test fails on the base.
- Group 3: Test first: a quote of a person in an open block stays the text of the person, and only the job blocks at the end of the block are blocks. The unit test fails on the base and on the head of group 2.
- Group 4: Test first: a job block marker on the last line of a declaration that a person leaves open bounds the block, as on the last line of a comment. The test fails on the head of group 3.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
