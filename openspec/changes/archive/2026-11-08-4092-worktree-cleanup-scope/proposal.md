# Proposal

## Why

`devops repos worktrees add` first runs `reclaim_merged_worktrees`, and that function removes any clean worktree of the repository whose tip heads a merged pull request, wherever its folder is (#4092). On 2026-11-07 it removed worktrees of other agents five times: folders outside `agent/worktrees` and stale folders inside it. A worktree with ignored files counts as clean, because `git status` hides them, so the removal also deleted ignored data (1.1 GB in one case). A worktree whose directory is missing is removed with no merge check.

## What Changes

- Limit the `add` reclaim to the worktrees under the folder that `add` manages: the resolved `agent/worktrees` folder of the data directory. The filter is in `reclaim_merged_worktrees`. A worktree outside the folder is kept, with no GitHub read, and a prunable record whose directory is missing and outside the folder is kept too.
- Keep a worktree under the folder when a file that `.gitignore` hides is present. The new function `count_ignored_paths` counts the `!!` entries of `git status --porcelain --ignored -z`. Only the reclaim calls it.
- Name each worktree that the reclaim leaves, with the reason (`outside the managed folder`, or the count of ignored paths), in the table output and in a `kept` list of the JSON report.
- Keep the removal rules inside the folder: the branch is merged, the worktree is clean and not locked, and it is not the current directory. The reclaim has no `--force` path.
- Leave `devops repos worktrees prune` unchanged. It keeps its scope, and it does not check ignored files.
- Move the existing reclaim tests so that every worktree they remove or read is under the managed folder, and move their `repo` fixture to `tests/git/conftest.py` with a new `managed` fixture.
- Say in `CONTRIBUTING.md` that the reclaim keeps worktrees outside the managed folder and worktrees with ignored files.
- The change carries a spec delta because the command, its output and its JSON report are observable. It does not change the CLI options, so `devops docs generate --sync-readme` has nothing new to write.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-worktrees-add`: The reclaim removes only worktrees under the managed folder that hold no ignored file, and names each worktree it keeps.

## Impact

- Code: `src/devops_cli/git/worktree_add.py`, `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`
- Documents: `CONTRIBUTING.md`
- Tests: `tests/git/test_repos_worktrees_reclaim_scope.py` (new), `tests/git/test_repos_worktrees_reclaim.py`, `tests/git/conftest.py` (new)

## Feasibility

Checked on 2026-11-08 with git 2.55.0, in temporary repositories and in the checkout:

- `reclaim_merged_worktrees` (`src/devops_cli/git/worktree_add.py`) calls `inventory_worktrees(repo_root)` with no folder filter. The inventory of this checkout lists 78 worktrees: 31 under `.data/agent/worktrees` and 47 elsewhere (`git worktree list --porcelain`). The first `worktrees add 4092` of this work removed a merged worktree of another agent outside the managed folder, so the defect is real.
- `git status --porcelain -z` prints nothing for a file that `.gitignore` hides, `git status --porcelain --ignored -z` prints `!! keep.log`, and `git worktree remove` without `--force` deletes the worktree with that file. The new test `test_ignored_file_keeps_worktree` shows the removal on the base.
- `git worktree list` marks a worktree with a missing directory as `prunable`, and `_decided_by_local_state` makes it removable before any merge check. The new test `test_missing_directory_outside_folder_is_kept` shows it.
- The set that the guard covers is the worktrees of the repository (`git worktree list`): 78 here, of which 47 are outside the managed folder and become kept; the 31 inside keep the current rules. The first group's `verify` runs the new tests, which build the three cases with real git.
- First check against the real system: `uv run devops ci fail-to-pass --base origin/main` lists `test_worktree_outside_managed_folder_is_kept`, `test_ignored_file_keeps_worktree` and `test_missing_directory_outside_folder_is_kept` as failing on the base. The ones that pass on both sides are `test_merged_clean_worktree_inside_folder_is_removed_and_named`, `test_missing_directory_inside_folder_is_removed_without_a_read` and `test_prune_keeps_its_scope_and_removes_a_merged_worktree_outside_the_folder`.
- Second check: `uv run devops openspec check` accepts the change folder.

## Existing Tool Considered

`git worktree list`, `git worktree remove` and `git status --ignored` already give every fact, and `pathlib.Path.is_relative_to` (standard library) decides the folder rule. No open tool decides who owns a worktree, and the change adds no dependency. The change builds one path comparison, one ignored-file count and one report list, so it costs about 40k tokens to write, little to keep (one comparison that the tests cover), and about 1 hour. The change deletes no internal code.
