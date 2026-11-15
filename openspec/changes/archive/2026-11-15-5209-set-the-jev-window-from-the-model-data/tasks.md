# Tasks

## 1. Read the window from the model data

Reads: `src/devops_cli/ai/jev.py`, `src/devops_cli/roadmap/jev_completeness.py`, `src/devops_cli/config/constants.py`.

Changes: `src/devops_cli/ai/jev.py`, `src/devops_cli/roadmap/jev_completeness.py`, `src/devops_cli/config/constants.py`, `tests/ai/test_jev.py`, `tests/roadmap/test_jev_completeness.py`, `tests/roadmap/test_jev_completeness_eval.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/fixtures/roadmap_eval/completeness/change-1653-complete/draft.diff`, `tests/fixtures/roadmap_eval/completeness/change-1653-hunk-removed/draft.diff`.

- [x] 1.1 Write the window test and watch it fail.
  - Verification: `$ uv run devops ci test tests/ai/test_jev.py`
- [x] 1.2 Read the window from genai-prices, take the cap from it, and trim the two fixtures.
  - Verification: `$ uv run devops ci test tests/ai/test_jev.py tests/roadmap/test_jev_completeness.py tests/roadmap/test_jev_completeness_eval.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
