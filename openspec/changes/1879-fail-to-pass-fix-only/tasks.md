# Tasks

## 1. The check runs only for a fix that changes the code under src

- [x] Add failing tests: the workflow's path filter and triggers, one replay job with no title, label or body variable, and the job condition against `CONST_DEFECT_TITLE_PATTERN` on fix and other titles
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py`
- [x] Add the path filter and the title condition to `.github/workflows/fail-to-pass.yml`, drop the `labeled` trigger, and delete the `self-check` job and the release-please case of the concurrency group
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py`
- [x] Describe when the check runs in `CONTRIBUTING.md`, and drop the escape line from Renovate's `prBodyNotes`
  - Verification: `uv run devops docs check`

## 2. The replay reads no title, label or body

- [x] Add failing tests: a run whose changed tests pass on base fails whatever `PR_TITLE`, `PR_LABELS` and `PR_BODY` say; the old options exit 2; a replay that cannot run names the next step
  - Verification: `uv run devops ci test tests/test_fail_to_pass.py`
- [x] Delete the escape parser, the label parser, the title and label classification, the report's `is_defect` and `escape_reason`, the three options and their help, `CONST_FAIL_TO_PASS_ESCAPE_PATTERN` and the not-applicable message; reword the report messages and update the snapshots
  - Verification: `uv run devops ci test tests/test_fail_to_pass.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1879-fail-to-pass-fix-only`
- Pending a person: if `Fail-to-Pass Check` ever becomes a required check of `main`, move the path scope from the workflow's `paths:` into the job's `if:`, because a workflow that a path filter skips leaves a required check Pending.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
