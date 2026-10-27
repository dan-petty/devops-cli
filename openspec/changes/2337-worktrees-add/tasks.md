# Tasks

## 1. The branch form in one place

- [x] 1.1 Write the failing invariant test in `tests/test_branch_form.py`: the branch types of the code equal the `changelog-sections` types of `release-please-config.json`, and the pattern of the `branch-name` hook in `.pre-commit-config.yaml` holds the expression that the code builds from them. Verify: `uv run devops ci test tests/test_branch_form.py` fails because the constants do not exist.
- [x] 1.2 Add `CONST_BRANCH_TYPES` and `CONST_BRANCH_SLUG_PATTERN` to `src/devops_cli/config/constants.py`. Verify: `uv run devops ci test tests/test_branch_form.py` passes.

## 2. Claim detection and the worktree

- [x] 2.1 Write the failing tests in `tests/test_repos_worktrees_add.py` with real repositories and a bare repository as `origin`: the worktree is created at the fetched tip with no upstream; an unknown type and a bad slug are refused first; a worktree of another slug, the standard directory and a branch of `origin` hold the issue; `feat/23370-x` and a local branch with no worktree hold nothing; no `origin` is named; a failed fetch creates nothing. Verify: `uv run devops ci test tests/test_repos_worktrees_add.py` fails because `add` does not exist.
- [x] 2.2 Add `src/devops_cli/git/worktree_add.py`: the reader of the issue of a branch, the claim check over the worktree list and `git ls-remote --heads origin`, and the creation with `git fetch origin main` and `git worktree add --no-track -b`. Add the messages to `src/devops_cli/lang/en/messages.py`. Verify: `uv run devops ci test tests/test_repos_worktrees_add.py` passes for the creation and the claim tests.

## 3. The command and the dry run

- [x] 3.1 Add the dry-run tests to `tests/test_repos_worktrees_add.py`: no command touches `origin`, the three commands are listed in order, nothing is created, and a held local worktree is still refused. Verify: `uv run devops ci test tests/test_repos_worktrees_add.py` fails on the new tests.
- [x] 3.2 Add `devops repos worktrees add` to `src/devops_cli/commands/repos.py` with `--type`, `--slug`, `--repo-dir` and `--dry-run`, the help text in `src/devops_cli/lang/en/help.py`, and the dry-run plan with `PlannedRequest`. Verify: `uv run devops ci test tests/test_repos_worktrees_add.py` passes, and a run in a scratch clone shows `git rev-parse --abbrev-ref @{u}` failing in the new worktree.
- [x] 3.3 Run `uv run devops docs generate --sync-readme`. Verify: `uv run devops ci docs` passes and `docs/CLI_REFERENCE.md` lists `devops repos worktrees add`.

## 4. The issue in `status`

- [ ] 4.1 Add failing tests to `tests/test_repos_worktrees.py`: `status --json` gives the issue of `fix/2337-other` and null for `main` and for a detached head, and the table shows an `Issue` column. Verify: `uv run devops ci test tests/test_repos_worktrees.py` fails on the new tests.
- [ ] 4.2 Add `issue` to `WorktreeEntry`, set it from the branch with the reader of `worktree_add.py`, and add the `Issue` column to the table in `src/devops_cli/commands/repos.py`. Run `uv run devops docs generate --sync-readme`. Verify: `uv run devops ci test tests/test_repos_worktrees.py tests/test_repos_worktrees_add.py` passes and `uv run devops ci docs` passes.

## 5. Documents and the real host

- [ ] 5.1 In `CONTRIBUTING.md` section 5, change the Branch row and the worktree row of the naming table, and the paragraph "The parts of a branch name", to name `devops repos worktrees add <issue> --type <type> --slug <slug>`, the standard path, and the refusal of a held issue. Verify: `uv run devops ci docs` passes and the text names the command.
- [ ] 5.2 From the main checkout of this host, run `add` for an issue that a real worktree holds, then for a free issue number with `--dry-run`, then for a free number. Verify: the first run exits 1 and names the holder, the second creates nothing, and the third creates `w-<issue>` that `worktrees status` lists with its issue.
- [ ] 5.3 Run the full `uv run devops ci --check --no-cache` in the worktree. Verify: every check passes.

## Workflow follow-up

- Removal of worktrees whose commits are merged, without a manual run of `prune`, is #2338.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
