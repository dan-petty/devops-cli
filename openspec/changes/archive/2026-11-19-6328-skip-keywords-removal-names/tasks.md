# Tasks

## 1. Behavior: skip Python keywords in removed names

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_removal_references.py`. Changes: `src/devops_cli/roadmap/stage/stage_removal_references.py`, `tests/roadmap/stage/test_roadmap_stage_removal_references.py`.

- [x] 1.1 Add tests to `tests/roadmap/stage/test_roadmap_stage_removal_references.py`: a hard keyword, a soft keyword and a passive keyword span give no removed name, `old_helper` stays a removed name, and a change folder that drops `and` gives no unhandled test reference.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`
- [x] 1.2 Add `_is_removable_identifier` to `src/devops_cli/roadmap/stage/stage_removal_references.py` with `keyword.iskeyword` and `keyword.issoftkeyword`, and call it from the passive and the active match paths of `find_removed_names`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_removal_references.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
