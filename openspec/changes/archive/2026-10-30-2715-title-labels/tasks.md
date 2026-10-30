# Tasks

## 1. The title gives the type and the scope

- [x] 1.1 Add failing tests: the labels of five titles with a model that proposes `type/security`, the comment for a scope with no label, a plain title, a label a person set, and the parts of a title
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py tests/test_roadmap_commit_title.py`
- [x] 1.2 Add `roadmap/commit_title.py`; replace the type mapping of the prompt by `CONST_ROADMAP_COMMIT_TYPE_LABELS`; derive the type and the scope in `roadmap/intake.py`; add the messages and the prompt text
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py tests/test_roadmap_commit_title.py tests/test_roadmap_stage_selection.py`
- [x] 1.3 Declare `type/epic` and nine scopes in `.github/labels.yml`
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py`
- [x] 1.4 Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- The labels of the open issues, and the labels `type/fix` and `type/release` that no file declares, are data. After the merge, an agent relabels the open issues with `devops gh issues edit` and removes the two labels.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
