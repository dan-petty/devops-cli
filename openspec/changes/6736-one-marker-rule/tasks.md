# Tasks

## 1. Read each job block marker with one rule

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/repair.py`, `src/devops_cli/roadmap/refine/refine_judge.py`, `src/devops_cli/roadmap/stage/stage_criteria.py`. Changes: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/refine/test_roadmap_refine_dependencies.py`.
Adds: `block_marker_of`, `close_blocks_before_markers`

- [ ] 1.1 Write the tests first. The cases `comment-open-above-alternatives` and `fence-open-above-the-refine-block` of `test_a_job_block_marker_ends_the_dependencies_section` in `tests/roadmap/refine/test_roadmap_refine_dependencies.py` give `[4989]`. `test_a_block_that_a_person_leaves_open_ends_at_the_first_job_block_marker` in `tests/roadmap/test_roadmap_body_hash.py` reads the refine section and the alternatives block after an open fence, an open `<pre>` block and an open `<?` block, and gives the text with the close before the first marker. The tests fail on the base
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_dependencies.py` fails on the base
- [ ] 1.2 Add `block_marker_of` to `src/devops_cli/roadmap/body_hash.py`, and call it in `_marker_span` and in `_ends_section`. Split a body at the first job block marker line in a block that no close ends, and read each part with `block_marker_spans`. Add `close_blocks_before_markers`, cut the body in that form in `extract_section_and_outside`, and parse it in that form in `body_dependencies`. Update the docstrings that the change makes wrong
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_dependencies.py` passes

## 2. Leave one job block after each write

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `tests/support/roadmap_refine.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, `tests/roadmap/test_roadmap_alternatives.py`.

- [ ] 2.1 Write the tests first. `test_a_block_that_a_person_opens_above_the_section_leaves_one_section_over_three_rounds` in `tests/roadmap/refine/test_roadmap_refine_block_markers.py` runs three refine rounds after a person opens a comment, a code fence or a `<pre>` block above a recorded section. The cases `person-fence-above-the-block`, `person-pre-above-the-block` and `person-fence-above-a-refine-section` of `test_an_open_block_leaves_one_block_and_an_unchanged_item_over_three_rounds` in `tests/roadmap/test_roadmap_alternatives.py` run three checks. Each round leaves one block and the close before the first marker. The fence and `<pre>` cases fail on the base
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_block_markers.py tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [ ] 2.2 Make `_with_block` in `src/devops_cli/roadmap/alternatives.py` find its block in the body that `close_blocks_before_markers` gives. The refine write keeps the outside text of `extract_section_and_outside`, which holds the close
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_repair.py tests/roadmap/stage/test_roadmap_stage_criteria.py` passes

## Criteria

- Group 2: Test first: over three rounds of the refine write and of the alternatives writer, a body with an open fence or an open `<pre>` above an existing job block holds one job block after each round. The test fails on the base.
- Group 1: Test first: for the body of case 2, `body_dependencies` gives [4989]. The test fails on the base.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
