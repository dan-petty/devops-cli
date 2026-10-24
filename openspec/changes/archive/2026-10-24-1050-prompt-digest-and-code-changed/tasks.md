# Tasks

## 1. Implement prompt digest start recording and arm refusal

- [x] 1.1 Write failing tests in `tests/test_review_profile.py` and `tests/test_review_defects.py`, and verify failure with `uv run devops ci test tests/test_review_profile.py tests/test_review_defects.py`
- [x] 1.2 Update `ReviewProfiler` in `src/devops_cli/ai/review/profile.py` to record `prompt_digest` at start and flag changes in `code_changed_during_run`
- [x] 1.3 Update `score_corpus_runs` in `src/devops_cli/ai/review/defects.py` to raise `ValidationError` for profiles with `code_changed_during_run: true`
- [x] 1.4 Update field comments in `profile.py`, warning text in `messages.py`, and documentation in `docs/SELF_IMPROVEMENT.md`
- [x] 1.5 Run tests and verify with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.6 Verify full CI gate passes with `uv run devops ci`

## Workflow follow-up

- Pending a person: review the pull request.
