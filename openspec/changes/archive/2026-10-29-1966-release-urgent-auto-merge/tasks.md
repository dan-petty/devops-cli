# Tasks

## 1. An urgent fix turns on auto-merge of the release pull request

- [x] Add a failing contract test: the step after `Run release-please`, its condition, its App token, the release pull request number from release-please's `pr` output, the four labels, `gh pr merge --auto --squash`, the `release-now` label and the rule in `RELEASE_CYCLE.md`
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py`
- [x] Add the step to `release.yml` and the label `release-now` to `.github/labels.yml`
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py tests/test_agents_md_claims.py tests/test_github_labels.py`
- [x] State the rule in `RELEASE_CYCLE.md`, amend ADR 0013, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1966-release-urgent-auto-merge`
- Pending a person: run `devops gh labels sync` after the merge, so the label `release-now` exists in the repository.
- Pending a person: at the first urgent fix, check in the `Release` run that the step turned on auto-merge, and that the merge of the release pull request started the run that created the release.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
