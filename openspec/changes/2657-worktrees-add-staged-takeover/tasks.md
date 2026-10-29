# Tasks

## 1. The branch form gives type and slug

- [x] 1.1 Write the failing test in `tests/test_branch_form.py`: `parse_branch("feat/2657-staged-takeover")` gives the type `feat`, the issue 2657 and the slug `staged-takeover`, and gives None for `main`, `feat/2657` and `wip/2657-x`. Verify: `uv run devops ci test tests/test_branch_form.py` fails because `parse_branch` does not exist.
- [x] 1.2 Add `BranchParts` and `parse_branch` to `src/devops_cli/git/branch_form.py` and make `issue_of_branch` use them. Verify: `uv run devops ci test tests/test_branch_form.py` passes.

## 2. The takeover of a staged branch

- [ ] 2.1 Write the failing tests in `tests/test_repos_worktrees_add.py` with a real bare `origin`: a branch with only the App's commits is taken over (worktree at the pushed tip, upstream `origin/<branch>`, `took over` and the commit count in the table and the JSON); a stopped run with three App commits reports 3; a branch with one commit by another author is refused and names the author; a branch with no commit past main is refused; an unset slug refuses and names the setting; `--type` and `--slug` left out come from the branch; a slug or a type that differs is an error that names the branch; a missing option with no staged branch exits 1; a refused run leaves no local branch. Update the existing holder tests so that their pushed branch has a commit by a person. Verify: `uv run devops ci test tests/test_repos_worktrees_add.py` fails on the new tests because `add` refuses every pushed branch.
- [ ] 2.2 Add the takeover to `src/devops_cli/git/worktree_add.py`: the `commits` field and the status `took over` of `WorktreeAddReport`, the read of the authors, the checks of the author and of the type and slug, the fetch with the explicit refspec, and `git worktree add --track`. Add the messages to `src/devops_cli/lang/en/messages.py`. Verify: `uv run devops ci test tests/test_repos_worktrees_add.py` passes.

## 3. The command and the dry run

- [ ] 3.1 Add the dry-run tests to `tests/test_repos_worktrees_add.py`: the four commands are listed in order, the output has the note on the staged branch, a dry run without `--slug` exits 2, and nothing is created. Change the dry-run test that counts three requests. Verify: `uv run devops ci test tests/test_repos_worktrees_add.py` fails on the new tests.
- [ ] 3.2 In `src/devops_cli/commands/repos.py` make `--type` and `--slug` optional, refuse a dry run without them, and render the takeover. Update the help in `src/devops_cli/lang/en/help.py` and the dry-run notes in `messages.py`. Verify: `uv run devops ci test tests/test_repos_worktrees_add.py tests/test_repos_worktrees_reclaim.py` passes.

## 4. Documents

- [ ] 4.1 In `CONTRIBUTING.md` (the worktree row of "Naming" and the paragraph on starting work), `docs/ROUTINE_TASKS.md` and `docs/SDLC.md` Phase 1, say that `worktrees add` takes over a staged branch and when it refuses one. Run `uv run devops docs generate --sync-readme`. Verify: `uv run devops ci docs` passes and the three documents name the takeover.
- [ ] 4.2 Run the full `uv run devops ci` once in the worktree. Verify: every check passes.

## Workflow follow-up

- The `stage` job that pushes the staged branch is #2654. The implement job that leaves the App's code commits is a sibling item of #2653.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
