# Tasks

## 1. Read only the comment at the end as the record block

- [x] Add the failing tests for a quote in a code span, a fence, an indented code block and a comment in the middle
  - Verification: `uv run pytest tests/test_roadmap_store_contract.py`
- [x] Parse the body with markdown-it-py in `split_record`, and delete the removal of every match
  - Verification: `uv run pytest tests/test_roadmap_store_contract.py tests/test_roadmap_refine.py tests/test_roadmap_intake.py`
- [x] Update `openspec/specs/roadmap-item-labels/spec.md`
  - Verification: `uv run devops openspec check`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2538-record-block-code-span`
