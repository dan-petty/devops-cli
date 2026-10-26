# Tasks

## 1. The template reads as a commit message

- [x] Add the failing test: the pull request template has no heading or rule line, and its `Change:` line names `openspec/changes/archive/<date>-<issue>-<slug>/`
  - Verification: `uv run devops ci test tests/test_pr_cmd.py -k pr_template`
- [x] Rewrite `.github/pull_request_template.md` as one comment and the two closing lines
  - Verification: `uv run devops ci test tests/test_pr_cmd.py -k pr_template`

## 2. Documents

- [x] `CONTRIBUTING.md`: the body is the squash commit message, what it holds, and what goes in a comment
  - Verification: `uv run devops docs check`
- [x] `docs/SDLC.md`, Phase 1, step 5: the branch holds `origin/main` at its first push, and an open pull request needs no rebase to catch up
  - Verification: `uv run devops docs check`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Checks

- [x] The OpenSpec gate and the fast static checks pass
  - Verification: `uv run devops openspec check`
  - Verification: `uv run devops ci --check --only lint,format,actionlint,zizmor`
