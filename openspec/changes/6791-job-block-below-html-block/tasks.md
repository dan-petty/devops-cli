# Tasks

## 1. Find a job block below an HTML block that a blank line ends

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`. Changes: `src/devops_cli/roadmap/body_hash.py`, `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, `tests/roadmap/test_roadmap_alternatives.py`.
Adds: `ends_at_a_blank_line`

- [x] 1.1 Write the tests first. In `tests/roadmap/test_roadmap_body_hash.py`, `job_block_bounds`, `extract_section_and_outside` and `close_blocks_before_markers` read a body with `</details>`, `<div>x</div>` or an `<img>` tag directly above the refine section and the alternatives block. They find both blocks, and the outside text holds a blank line before each start marker. A marker in a closed fence in a `<details>` part, or in a closed `<pre>` or `<?` block, stays the text of the person. A marker that a person writes in an HTML block that only a blank line ends also stays their text. The cases are a lone start marker in a `<details>` block and a marker pair in a `<div>` block. Two more cases are a fence line after a marker in a `<div>` block, and a lone alternatives start marker in a `<div>` block. For each case, `close_blocks_before_markers` and `closed_body` give the body, so its render does not change. A job block that a line of the person follows in the same HTML block stays unread. In `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, a person puts a `<details>` part or `<div>x</div>` directly above a recorded section, and three refine rounds leave one section. Three refine rounds keep a `<details>` block of a person with a start marker in it. In `tests/roadmap/test_roadmap_alternatives.py`, three checks on a body with an HTML line directly above the block leave one block. A lone start marker in a `<div>` block of a person stops no write. The tests of the issue cases fail on the base. The tests of the text of a person pass on the base
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_block_markers.py tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/body_hash.py`, add `ends_at_a_blank_line` and `_html_block_end`. `_parts` starts a new part at a job block marker line in a top-level HTML block that only a blank line ends. The line must start the job blocks at the end of the body (`_are_job_blocks`), and no text may follow them. The cut must leave no block open (`close_open_block`). The part before keeps its tokens up to that HTML block. Update the docstrings of the module and of the readers
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_repair.py` passes

## 2. Read the record below an HTML block that a blank line ends

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/stores/test_roadmap_store_record_block.py`.

- [x] 2.1 Write the tests first. In `tests/roadmap/stores/test_roadmap_store_record_block.py`, a person puts `<details>`, `<div>` or `<div>x</div>` directly above the record, also with CRLF line breaks. The read gives the record and the body of the person. The next record write gives one record block that CommonMark parses as the last HTML block, with the old keys. The text of the person keeps its rendered form. The Hypothesis property of #6785 also puts `<div>` and `</details>` on any line above the record. Its example puts `<div>` directly above the record. Each parametrized test and the example fail on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_record_block.py` fails on the base
- [x] 2.2 In `split_record` of `src/devops_cli/roadmap/stores/store.py`, give the span of the last block to `_record_below_open_block`. It reads the record line when that block starts above the line and `ends_at_a_blank_line` of `body_hash.py` is true for it. Update the docstrings of `_record_below_open_block` and `split_record`
  - Verification: `$ uv run devops ci test tests/roadmap/stores tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_block_markers.py` passes

## 3. State the rule in the roadmap document

Kind: other. Reads: `src/devops_cli/roadmap/stores/store.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 In the job record paragraph of `docs/ROADMAP_WORKFLOW.md`, say that only a blank line ends an HTML block such as `<details>`. A person can remove that blank line above the record. The read then ends the block at the record line, and the next write puts the blank line back
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: Test first: for a body with `</details>` and with `<div>x</div>` directly above the start marker, `job_block_bounds` and `extract_section_and_outside` find the block. The test fails on the base.
- Group 1: Test first: one refine write and one alternatives write on such a body leave one job block.
- Group 1: Test first: a marker that a person writes in such an HTML block stays their text. A write keeps the body and its render.
- Group 2: Test first: `split_record` reads the record below `<details>`, and the next write leaves one record with the old keys. The test fails on the base.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
