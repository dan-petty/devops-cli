# Tasks

## 1. Find a job block below an HTML block that a blank line ends

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`. Changes: `src/devops_cli/roadmap/body_hash.py`, `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, `tests/roadmap/test_roadmap_alternatives.py`.
Adds: `ends_at_a_blank_line`

- [x] 1.1 Write the tests first. In `tests/roadmap/test_roadmap_body_hash.py`, `job_block_bounds`, `extract_section_and_outside` and `close_blocks_before_markers` read a body with `</details>`, `<div>x</div>` or an `<img>` tag directly above the refine section and the alternatives block. They find both blocks, and the outside text holds a blank line before each start marker. A marker in a closed fence in a `<details>` part, in a closed `<pre>` block or in a closed `<?` block stays the text of the person. In `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, a person puts a `<details>` part or `<div>x</div>` directly above a recorded section, and three refine rounds leave one section. In `tests/roadmap/test_roadmap_alternatives.py`, three checks on such a body leave one block. Each new test fails on the base, except the quote test, which passes on the base and on the head
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_block_markers.py tests/roadmap/test_roadmap_alternatives.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/body_hash.py`, add `ends_at_a_blank_line` and `_html_block_end`. `_parts` starts a new part at the first job block marker line after the first line of a top-level HTML block that only a blank line ends, and cuts the tokens of the part before after that block. Update the docstrings of the module and of `_parts`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_repair.py` passes

## 2. Read the record below an HTML block that a blank line ends

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/stores/test_roadmap_store_record_block.py`.

- [x] 2.1 Write the tests first. In `tests/roadmap/stores/test_roadmap_store_record_block.py`, a person puts `<details>`, `<div>` or `<div>x</div>` directly above the record, also with CRLF line breaks. The read gives the record and the body of the person. The next record write gives one record block that CommonMark parses as the last HTML block, with the old keys. The text of the person keeps its rendered form. The Hypothesis property of #6785 also opens `<div>` and `</details>` on any line. Each parametrized test fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_record_block.py` fails on the base
- [x] 2.2 In `split_record` of `src/devops_cli/roadmap/stores/store.py`, give the span of the last block to `_record_below_open_block`. It reads the record line when that block starts above the line and `ends_at_a_blank_line` of `body_hash.py` is true for it. Update the docstrings of `_record_below_open_block` and `split_record`
  - Verification: `$ uv run devops ci test tests/roadmap/stores tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_block_markers.py` passes

## 3. State the rule in the roadmap document

Kind: other. Reads: `src/devops_cli/roadmap/stores/store.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 In the job record paragraph of `docs/ROADMAP_WORKFLOW.md`, say that a blank line ends an HTML block such as `<details>`. When a person removes that blank line above the record, the read ends the block at the record line, and the next write puts the blank line back
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: Test first: for a body with `</details>` and with `<div>x</div>` directly above the start marker, `job_block_bounds` and `extract_section_and_outside` find the block. The test fails on the base.
- Group 1: Test first: one refine write and one alternatives write on such a body leave one job block.
- Group 2: Test first: `split_record` reads the record below `<details>`, and the next write leaves one record with the old keys. The test fails on the base.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
