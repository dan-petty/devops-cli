# Tasks

## 1. Close the open block before the job blocks

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/stores/test_roadmap_store_record_block.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`.

- [x] 1.1 Write `test_a_record_write_keeps_a_job_block_in_an_open_block_readable`: a record write on a body with the refine block at the end of an open fence or `<pre>` keeps the section that a read finds, and the record. It fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_record_block.py` fails on the base
- [x] 1.2 In `closed_body`, call `close_blocks_before_markers` before the close of the end, and update the docstring
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_record_block.py` passes
- [x] 1.3 Make the round test of the open fence and the open `<pre>` assert one write that replaces the section in place, as its docstring asks when a round reads the record
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_block_markers.py` passes
