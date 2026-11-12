# Tasks

## 1. Behavior

- [x] 1.1 Write the tests of the reason comment: no comment for the usual fields, one line for a related item, the Priority reason only for P1-High
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_reason_comment.py`
- [x] 1.2 Give only the facts that the labels do not show, and post no comment when there is none
  - Verification: `$ uv run devops ci test tests/roadmap/intake/`

## 2. Documents

- [x] 2.1 Tell what the reason comment holds in `docs/roadmap/intake.md`
  - Verification: `$ uv run devops ci docs`
