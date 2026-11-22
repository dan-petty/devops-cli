# Tasks

## 1. Read the record below a block that a person opens

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/stores/github_store.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/stores/test_roadmap_store_record_block.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`, `tests/roadmap/stores/test_roadmap_github_store_record_writes.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`.

- [x] 1.1 Write the tests first. In `tests/roadmap/stores/test_roadmap_store_record_block.py`: a written body in which a person then opens a backtick fence, a tilde fence, a `<pre>` block or a comment above the record, also with CRLF line breaks, gives the record and the body of the person; the next record write gives one record block that CommonMark parses as the last HTML block, with the keys of the old record, and the text of the person keeps its rendered form; a fence above the refine block and the record gives one record block after the next write, and the same section; a quote with no JSON object in an open fence stays in the body with no warning; and a Hypothesis property opens a block on any line of a written body. In the contract suite, a mark write to such an issue keeps the old keys and one record block in each adapter. In `tests/roadmap/stores/test_roadmap_github_store_record_writes.py`, two mark writes from one read send one `PATCH` each, keep the old keys and count no lost edit. In `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, a person opens a fence or a `<pre>` block above the section on GitHub, and three refine rounds leave one section and one record block. Each new test but the quote test fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_record_block.py tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/stores/test_roadmap_github_store_record_writes.py tests/roadmap/refine/test_roadmap_refine_block_markers.py` fails on the base
- [x] 1.2 In `split_record` of `src/devops_cli/roadmap/stores/store.py`, when the last block is not the record, read the last line of the body as the record when CommonMark parses that line alone as the record block, it holds a JSON object, and `close_open_block` of `body_hash.py` closes a block that the text before it leaves open. Import `close_open_block` inside the function. Update the docstrings of `split_record` and `with_record`
  - Verification: `$ uv run devops ci test tests/roadmap/stores tests/roadmap/test_roadmap_body_hash.py tests/roadmap/refine/test_roadmap_refine_block_markers.py` passes

## 2. State the read in the roadmap document

Kind: other. Reads: `src/devops_cli/roadmap/stores/store.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 In the job record paragraph of `docs/ROADMAP_WORKFLOW.md`, say that a read ends a block that a person opens above the record at the record, and that the next write closes the block
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- #6791: an HTML block that a blank line ends, directly above a job block marker, hides the job block. This change reads no record directly below such a block either. A person makes this case with one line, such as `<details>`, directly above the record.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
