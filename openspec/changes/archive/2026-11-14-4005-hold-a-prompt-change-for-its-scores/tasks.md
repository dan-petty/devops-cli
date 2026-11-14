# Tasks

## 1. Refuse a prompt change with no scores

Reads: `src/devops_cli/roadmap/implement/implement_pull.py`, `tests/roadmap/test_roadmap_draft_readiness.py`.

Changes: `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_draft_readiness.py`.

- [x] 1.1 Write the six score cases, and watch them fail.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py`
- [x] 1.2 Add `Draft.files`, read the compare for every kind, and add the score rule and its message.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_draft_readiness.py`
- [x] 1.3 Pass the local diff of the ready step to the draft.
  - Verification: `$ uv run devops ci test tests/roadmap/implement`

## 2. Accept the score lines in the body

Reads: `src/devops_cli/roadmap/pull_form.py`, `tests/roadmap/test_roadmap_pull_form.py`.

Changes: `tests/roadmap/test_roadmap_pull_form.py`.

- [x] 2.1 Add the body test of the two lines after `Change:`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
