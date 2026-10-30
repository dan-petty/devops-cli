# Tasks

## 1. The git fake, the transcripts and the contract suite

- [x] Add the failing contract suite and the scenarios for the git commands that the code already starts through the runner: `read_file_at_revision`, `list_changed_files`, `resolve_merge_base`, `is_git_clean`, `get_latest_git_tag`, the worktree functions, `own_source_state` and `get_repo_origin_name`
  - Verification: `uv run devops ci test tests/test_git_contract.py`
- [x] Add `GitFake`, the `git_fake` fixture and the refusal of real git in a test that uses it
  - Verification: `uv run devops ci test tests/test_git_contract.py`
- [x] Add the recorder (`tests/support/git_recording.py`) and record the transcripts with the real git
  - Verification: `uv run python -c "import sys; from tests.support.git_recording import main; sys.exit(main(['--check']))"`
- [x] Give `own_source_state` a package directory parameter, and move `tests/test_git_worktree.py`, `tests/test_core_repo.py` and the tests of `tests/test_git_operations.py` that need no GitPython to the fake
  - Verification: `uv run devops ci test tests/test_git_worktree.py tests/test_core_repo.py tests/test_git_operations.py`

## 2. The GitPython users run git through the runner

- [x] Add failing tests: the invariant that no module of `src/` imports GitPython, and the scenarios and tests of `clone_repo`, `fetch_all`, `pull_tracking`, `create_branch`, `commit_snapshot`, `list_branches`, `delete_merged_branches`, `current_branch` and `extract_git_co_changes`
  - Verification: `uv run devops ci test tests/test_architectural_invariants.py tests/test_git_contract.py tests/test_git_operations.py`
- [x] Move the three users to the runner, accept the two date keys in `CONST_GIT_ACCEPTED_ENV`, and move `tests/test_git_operations.py`, `tests/test_ssh_host_keys.py`, `tests/test_ai_research_forage.py` and `tests/test_review_score.py` to the fake or to the `git` fixture
  - Verification: `uv run devops ci test tests/test_git_operations.py tests/test_ssh_host_keys.py tests/test_ai_research_forage.py tests/test_review_score.py tests/test_subprocess_env_boundary.py tests/test_repos.py`
- [x] Remove GitPython from `pyproject.toml` and `uv.lock`
  - Verification: `uv run devops ci deps lockfile`

## 3. The row that records the transcripts again

- [x] Add the failing test of the row, then the `git` row in `get_check_specs` and its title
  - Verification: `uv run devops ci test tests/test_ci.py`
- [x] Run the row and measure it
  - Verification: `uv run devops ci --only git`

## 4. Documents

- [ ] Describe the git seam, the fake, the contract suite and the row in `docs/TESTING.md`, remove the GitPython manual from the knowledge base, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 5. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2146-one-git-seam-and-fake`

## Workflow follow-up

- #2174 and #2178 to #2183 move the other test files to the fake, and refuse real git in every test when the last one has moved.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
