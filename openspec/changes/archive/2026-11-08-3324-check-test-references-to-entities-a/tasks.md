# Tasks

## 1. Implement removal-reference scanner

Reads: `src/devops_cli/roadmap/stage/stage_removal_references.py`, `tests/roadmap/stage/test_roadmap_stage_removal_references.py`. Changes: `src/devops_cli/roadmap/stage/stage_removal_references.py`, `tests/roadmap/stage/test_roadmap_stage_removal_references.py`.

- [x] 1.1 Add failing unit tests for removed name extraction and reference scanning in `tests/roadmap/stage/test_roadmap_stage_removal_references.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`
- [x] 1.2 Implement `find_removed_names` and `scan_removal_references` in `src/devops_cli/roadmap/stage/stage_removal_references.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`

## 2. Integrate removal scan into stage workflow

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_removal_references.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_removal_references.py`.

- [x] 2.1 Add failing tests for stage failure on unhandled test references and warning on unhandled source references
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`
- [x] 2.2 Wire `scan_removal_references` into `_settle` / `_stage_one` in `src/devops_cli/roadmap/stage/stage.py` and add message strings in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`

## 3. Verify checks and archive change

- [x] 3.1 Run test suite and check OpenSpec validation
  - Verification: `$ uv run devops openspec check`
