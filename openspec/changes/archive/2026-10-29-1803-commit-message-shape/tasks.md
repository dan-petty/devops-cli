# Tasks

## 1. The title summary has at most 60 characters

- [x] Add a failing test: the `Semantic PR title` step accepts a summary of 60 characters, refuses one of 61, and its error names the limit and `CONTRIBUTING.md`
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py`
- [x] Set `subjectPattern` and `subjectPatternError` on the step in `.github/workflows/pr-title.yml`
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py`
- [x] State the title, body and branch-commit rules in `CONTRIBUTING.md` section 4 and its naming table, point `docs/SDLC.md`, `docs/ROUTINE_TASKS.md` and the pull request template to them, and delete the two duplicate rules
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. Agent prose puts the result and the decision first

- [x] Add the paragraph to `src/devops_cli/ai/tasks/style_ste100.md` and update the style request snapshot
  - Verification: `uv run devops ci test tests/test_ai_client_style_request.py tests/test_ai_client_structured.py`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1803-commit-message-shape`

## Workflow follow-up

- #2585: `devops pr check-readiness` warns when a pull request body passes 1,000 characters before the trailers.
- Pending a person: after 50 more squash commits on `main`, measure the titles and bodies again with the method of the proposal's Feasibility section, and post the numbers on #1803.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
