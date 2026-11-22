# Tasks

## 1. Close an open block before the record block

Kind: behavior. Reads: `src/devops_cli/roadmap/body_hash.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/stores/test_roadmap_store_record_block.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`.

- [x] 1.1 Write `tests/roadmap/stores/test_roadmap_store_record_block.py`: an open backtick fence, an open tilde fence, an open `<!--` and an open `<pre>` each give the record back with the close in the body; a body with no open block is written with the same text as before; a second write keeps the body and its body hashes; the code of an open fence keeps its rendered form; and a Hypothesis property over Markdown lines reads each record back. Add `test_a_body_that_leaves_a_block_open_keeps_its_record_and_settles` to the contract suite, which runs four rounds of a hash write against each adapter. Each new test but the one of a body with no open block fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_record_block.py tests/roadmap/stores/test_roadmap_store_contract.py` fails on the base
- [x] 1.2 In `with_record` of `src/devops_cli/roadmap/stores/store.py`, take one line break off the end of the body, close the open block with `close_open_block`, and keep the body as it is when no block is open. Import `close_open_block` inside the function. Update the docstrings of `with_record` and `split_record`
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_record_block.py tests/roadmap/stores/test_roadmap_store_contract.py` passes

## 2. Count no lost edit for the close

Kind: behavior. Reads: `src/devops_cli/telemetry/instruments.py`. Changes: `src/devops_cli/roadmap/stores/github_store.py`, `tests/roadmap/stores/test_roadmap_github_store_record_writes.py`.

- [x] 2.1 Write `test_the_close_of_a_block_that_the_body_leaves_open_is_no_lost_edit`: a mark write to a body that ends in an open fence sends one `PATCH`, keeps the mark and counts no lost edit. It fails on the base, which raises `RoadmapRecordMarkLostError`
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_record_writes.py` fails on the base
- [x] 2.2 In `_edit_issue` of `src/devops_cli/roadmap/stores/github_store.py`, compare the body that the store reads back with the body that `split_record` gives for the text that it wrote
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_github_store_record_writes.py` passes

## 3. State the close in the roadmap document

Kind: other. Reads: `src/devops_cli/roadmap/stores/store.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 In the job record paragraph of `docs/ROADMAP_WORKFLOW.md`, say that a record write closes a code fence or an HTML block that the body leaves open at its end
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
