# Tasks

## 1. Failing tests

- [x] 1.1 Add failing tests in `tests/test_roadmap_intake.py` for a source with a sub-issue of a near-identical title, a sub-issue of another issue, a candidate with no source, and a parent in another repository, over the in-memory store and over the GitHub fake
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py`

## 2. Intake leaves out the sub-issues of the source

- [x] 2.1 Add `parent` to `IssueRecord`, read it from `parent_issue_url` in `github_store.py`, and seed it in the in-memory store and the GitHub fake
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py`
- [x] 2.2 Add the sub-issues of the source issue to the numbers `_Planner._decide` keeps out of the shortlist, and update the module documentation of `intake.py`
  - Verification: `uv run devops ci test tests/test_roadmap_intake.py`
- [x] 2.3 Update the help text of `--source` and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Verification and checks

- [ ] 3.1 Verify the OpenSpec gate passes
  - Verification: `uv run devops openspec check`
- [ ] 3.2 Verify the full CI suite passes
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
