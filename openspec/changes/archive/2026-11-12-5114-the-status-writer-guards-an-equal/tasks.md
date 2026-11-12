# Tasks

## 1. The guard of an equal label (behavior)

- [x] 1.1 Write failing tests: the writer refuses the marks and the body of an equal label that a person changed since the read, refine writes nothing for a Ready item that a person moved during the round, and both stores refuse `set_marks` with `unchanged` after a person's change
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_status_sync.py tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/refine/test_roadmap_refine_one_write.py`
- [x] 1.2 Give `set_marks` the keyword `unchanged` in the store protocol, the GitHub store and the fake store, and pass `unchanged=ItemField.STATUS` from `write_status` when the label is equal
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_status_sync.py tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/refine/test_roadmap_refine_one_write.py`

## 2. Test doubles (test-only)

- [x] 2.1 Let the test doubles that override `set_marks` forward the new keyword
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_deferred.py tests/roadmap/refine/test_roadmap_refine_gateway_failures.py tests/roadmap/stage/test_roadmap_stage_item_writes.py`

## 3. Documents

- [x] 3.1 Say in `docs/ROADMAP_WORKFLOW.md` that the writer refuses the marks of an equal label that someone changed since the read
  - Verification: `$ uv run devops ci docs`
