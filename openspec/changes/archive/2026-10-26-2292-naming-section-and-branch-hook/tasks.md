# Tasks

## 1. Failing tests

- [x] Add the tests that fail on `main`: the pattern of the hook on accepted and refused names, the entry for `main`, the Naming table and the types, and the retired branch forms
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py tests/test_agents_md_claims.py`

## 2. Hook

- [x] Add the `branch-name` entry of `no-commit-to-branch` to `.pre-commit-config.yaml`
  - Verification: `uv run pre-commit run branch-name --all-files`

## 3. Documentation

- [x] Add the section "Naming" to `CONTRIBUTING.md`, move the routine tasks to section 6, and replace the statements of the branch form in `docs/SDLC.md`, `docs/ROUTINE_TASKS.md` and `docs/DEVCONTAINER_USAGE.md` with links
  - Verification: `uv run devops docs check`

## 4. Verification and static checks

- [x] Verify the fail-to-pass check run against `origin/main`
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify that the full static checks pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: the eight `implement_issue_*` branches on `origin` break the form. Move each to a name in the form or delete it, after you check that no open pull request or session uses it.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
