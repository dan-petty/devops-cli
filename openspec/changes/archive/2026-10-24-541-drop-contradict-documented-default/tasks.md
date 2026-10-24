# Tasks

## 1. Remove contradict-documented-default template

- [x] 1.1 Add failing test showing `select_templates(["contradict-documented-default"])` raises `ValueError` (`uv run pytest tests/test_review_defects.py -k test_select_templates_rejects_removed_contradict_documented_default`)
- [x] 1.2 Remove `_DOCUMENTED_DEFAULT`, `_OPPOSITES`, `_contradict_defaults`, and `contradict-documented-default` template definition from `src/devops_cli/ai/review/defects.py` (`uv run pytest tests/test_review_defects.py -k test_select_templates_rejects_removed_contradict_documented_default`)
- [x] 1.3 Remove obsolete test cases and update corpus test in `tests/test_review_defects_infra.py` (`uv run pytest tests/test_review_defects_infra.py`)
- [x] 1.4 Delete template row in `docs/SELF_IMPROVEMENT.md` and regenerate documentation (`uv run devops docs generate --sync-readme`)
- [x] 1.5 Run CI gate and verify coverage (`uv run devops ci`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
