# Tasks

## 1. The claim sets the Status In Progress

Kind: feature. Changes: `tests/roadmap/test_roadmap_claim.py`, `tests/core/test_repos_worktrees_add.py`, `tests/git/test_repos_worktrees_reclaim.py`, `src/devops_cli/roadmap/pull_status.py`, `src/devops_cli/roadmap/claim.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 1.1 Write the tests first: the claim moves no Status, New, Ready and Planned to In Progress on both store adapters; it keeps Blocked (also a stop of the implement job), In Progress and In Review; `add` reports `status_error` and warns when the Status write fails; a dry run lists the Status write with its condition and writes nothing.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_claim.py tests/core/test_repos_worktrees_add.py`
- [x] 1.2 Add `set_claimed_status` and `progress_as_agent`, call it from `_claimed` after a claim that is made, add `status_error` to the report and its warning, and list the Status requests in the dry run.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_claim.py tests/core/test_repos_worktrees_add.py tests/git/test_repos_worktrees_reclaim.py`

## 2. Documents

- [x] 2.1 Name the Status write in `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROADMAP_WORKFLOW.md` and the help of `devops repos worktrees add`, and generate the command reference again.
  - Verification: `$ uv run devops ci --check --only docs`
