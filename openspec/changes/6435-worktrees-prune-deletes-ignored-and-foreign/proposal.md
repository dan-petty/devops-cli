# Proposal

## Why

`devops repos worktrees prune --confirm` removes a clean worktree whose tip heads a merged pull request in any folder, and `git worktree remove` deletes the files that `.gitignore` hides. It has removed agent scratch files, a local `.env` and worktrees that other tools made outside the repository (#6435). The reclaim of `devops repos worktrees add` already keeps a worktree outside the managed folder and a worktree that holds ignored paths, but prune never asks that rule. One shared scope function makes the two commands agree, and the help text and `CONTRIBUTING.md` state the scope.

## What Changes

- Add `scope_refusal(entry, *, managed_root)` to `src/devops_cli/git/worktree_inventory.py`: it returns the reason that keeps a worktree out of a removal, or None when the worktree is in scope.
- Call `scope_refusal` in `_split_by_scope` of `src/devops_cli/git/worktree_add.py` in place of its two inline scope checks, so the reclaim and prune take one rule.
- Rename the three kept reasons in `src/devops_cli/lang/en/messages.py` to `worktrees_kept_outside`, `worktrees_kept_ignored` and `worktrees_kept_ignored_unknown`, with the managed folder in the outside reason and the count and its singular or plural form in the ignored reason.
- Give `_decide`, `plan_prune` and `prune_worktrees` in `src/devops_cli/git/worktree_inventory.py` the resolved managed folder, and call `scope_refusal` after the local-state decision and before the merged-pull request read.
- Pass the managed folder from `worktrees_prune` in `src/devops_cli/commands/repos.py` and from `reclaim_merged_worktrees` in `src/devops_cli/git/worktree_add.py`, and give the direct caller in `tests/git/test_repos_worktrees_reclaim.py` the same keyword.
- Move the worktrees of the prune tests in `tests/git/test_repos_worktrees.py` under the managed folder, because prune now refuses a worktree outside it.
- State the scope in the docstring of `worktrees_prune` and in `HELP.repos.worktrees_prune` and `HELP.repos.worktrees_force`, and regenerate `docs/commands/repos.md`.
- Add the scope paragraph to section 4 of `CONTRIBUTING.md`.
- Add the scope requirements to the spec delta of `repos-worktrees-prune` and change the reclaim requirement and the prune scope scenario of `repos-worktrees-add`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-worktrees-prune`: An ignored path keeps a worktree, A worktree outside the managed folder stays, Prune and the reclaim share one scope decision, Force removes a refused worktree, The prune help states the scope, A merged pull request makes a worktree removable
- `repos-worktrees-add`: A reclaim keeps a worktree that it does not manage

## Impact

- Code: `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/commands/repos.md`, `CONTRIBUTING.md`
- Tests: `tests/git/test_repos_worktrees.py`, `tests/git/test_repos_worktrees_reclaim_scope.py`, `tests/git/test_repos_worktrees_reclaim.py`, `tests/commands/test_repos.py`

## Feasibility

- The probe line "The path `src/devops_cli/git/worktree_inventory.py` is a file of the staging commit." confirms the module that decides a prune, and that module holds `src/devops_cli/git/worktree_inventory.py:425:` `local = _decided_by_local_state(entry, force=force, current_dir=current_dir)`, so a prune asks no scope rule today.
- The probe line "The path `src/devops_cli/git/worktree_add.py` is a file of the staging commit." confirms the module that holds the reclaim, and that module holds `src/devops_cli/git/worktree_add.py:283:` `def reclaim_merged_worktrees(repo_root: Path, *, dry_run: bool = False) -> ReclaimResult:`, which the plan changes.
- The probe line "The path `CONTRIBUTING.md` is a file of the staging commit." confirms the document that states the scope.
- The probe line "The path `.data/agent/scratch/note.md` is no file of the staging commit. No commit in the history deleted or renamed it." names the ignored file of the reproduction: it is data inside a worktree and never a repository file, so its absence is no false premise.
- `read_file` of `src/devops_cli/git/worktree_inventory.py` lines 417-433 showed that prune decides each worktree with local state and then the merged pull request, and asks no scope rule: `src/devops_cli/git/worktree_inventory.py:425:` `local = _decided_by_local_state(entry, force=force, current_dir=current_dir)`.
- `read_file` of `src/devops_cli/git/worktree_inventory.py` lines 386-414 showed that force returns before every other local rule, so the scope check that follows it keeps force first: `src/devops_cli/git/worktree_inventory.py:400:` `if force:`.
- `read_file` of `src/devops_cli/git/worktree_inventory.py` lines 445-481 showed that the dry run asks the local-state rule and then plans a read for every other worktree, so it must ask the scope too: `src/devops_cli/git/worktree_inventory.py:459:` `local = _decided_by_local_state(entry, force=force, current_dir=current_dir)`.
- `read_file` of `src/devops_cli/git/worktree_inventory.py` lines 222-250 showed the ignored counter that prune must ask: `src/devops_cli/git/worktree_inventory.py:227:` `def count_ignored_paths(worktree_dir: Path) -> int | None:`, whose docstring states that `git worktree remove` deletes the ignored data (#4092).
- `read_file` of `src/devops_cli/git/worktree_add.py` lines 256-280 showed the reclaim's two inline scope checks: `src/devops_cli/git/worktree_add.py:272:` `if not Path(entry.path).resolve().is_relative_to(folder):` and `src/devops_cli/git/worktree_add.py:274:` `elif (ignored := count_ignored_paths(Path(entry.path))) is None:`.
- The issue cites `src/devops_cli/git/worktree_add.py:259` for the outside check; at this commit that line holds the docstring `src/devops_cli/git/worktree_add.py:259:` `"""The worktrees that the reclaim may remove, and the ones it keeps without a GitHub read.` and the outside check sits at line 272, so the line number is stale and the code is present, not removed.
- `read_file` of `src/devops_cli/git/worktree_add.py` lines 240-320 showed the second caller of `plan_prune`: `src/devops_cli/git/worktree_add.py:301:` `return ReclaimResult(kept=kept, requests=plan_prune(entries, repo=repo).requests)`. Group 3 changes that module for this call.
- `read_file` of `src/devops_cli/commands/repos.py` lines 930-981 showed the command caller and the docstring that carries no scope: `src/devops_cli/commands/repos.py:962:` `"""Remove the worktrees whose tip heads a merged pull request; preview unless --confirm."""` and `src/devops_cli/commands/repos.py:971:` `report = plan_prune(entries, repo=origin, force=force)`.
- `read_file` of `src/devops_cli/lang/en/messages.py` lines 684-698 showed the reason that gains the folder: `src/devops_cli/lang/en/messages.py:690:` `worktrees_add_kept_outside: str = "outside the managed folder"`.
- `references` for `worktrees_add_kept` listed three files: `src/devops_cli/git/worktree_add.py`, which holds `src/devops_cli/git/worktree_add.py:273:` `kept.append(_kept(entry, messages.worktrees_add_kept_outside))`; `src/devops_cli/lang/en/messages.py`, which holds `src/devops_cli/lang/en/messages.py:690:` `worktrees_add_kept_outside: str = "outside the managed folder"`; and `src/devops_cli/commands/repos.py`, which holds `src/devops_cli/commands/repos.py:708:` `MESSAGES.repos.worktrees_add_kept_line.format(path=item.path, reason=item.reason),` and keeps that message name.
- `read_file` of `src/devops_cli/lang/en/help.py` lines 650-675 showed the help that gains the scope: `src/devops_cli/lang/en/help.py:660:` `worktrees_prune: str = (` and `src/devops_cli/lang/en/help.py:664:` `worktrees_force: str = (`.
- `read_file` of `src/devops_cli/git/worktree_add.py` lines 95-125 showed the folder function that the plan keeps where it is: `src/devops_cli/git/worktree_add.py:106:` `def managed_folder(repo_root: Path) -> Path:`. It reads the agent worktrees subpath through `resolve_data_path`; the plan uses the function and writes no value or bound of that constant.
- `read_file` of `tests/git/conftest.py` showed the fixture that the moved prune tests take: `tests/git/conftest.py:31:` `def managed(isolate_data_dir: Path) -> Path:`.
- `read_file` of `tests/git/test_repos_worktrees.py` lines 380-720 showed that the prune tests build their worktrees outside the managed folder: `tests/git/test_repos_worktrees.py:404:` `merged = tmp_path / "wt_merged"`, and assert their removal at `tests/git/test_repos_worktrees.py:411:` `assert (result.exit_code, merged.exists(), github_api.requested) == (0, False, [request])`. Group 1 moves them under the managed folder and its verify runs that module.
- `read_file` of `tests/git/test_repos_worktrees_reclaim_scope.py` lines 1-242 showed the test that pins today's prune scope, `tests/git/test_repos_worktrees_reclaim_scope.py:232:` `def test_prune_keeps_its_scope_and_removes_a_merged_worktree_outside_the_folder(`, and the reason prefix it asserts at `tests/git/test_repos_worktrees_reclaim_scope.py:35:` `OUTSIDE = "outside the managed folder"`. Group 3 rewrites the first, and group 2 keeps the second as the prefix of the new reason.
- `read_file` of `tests/git/test_repos_worktrees_reclaim.py` lines 240-330 showed the direct caller of `prune_worktrees` that the new keyword reaches: `tests/git/test_repos_worktrees_reclaim.py:277:` `report = prune_worktrees(repo, entries, repo="example-org/app", confirm=True)`. Group 3 gives it the managed folder and runs that module.
- The review finding on the verify of the group that moves the prune fixtures is answered: the move is group 1, whose verify is `uv run devops ci test tests/git/test_repos_worktrees.py`, and group 3's verify runs that module too, so no step changes a test that its verify does not run.
- The review finding on the missing caller path is answered by `src/devops_cli/git/worktree_add.py:301:` `return ReclaimResult(kept=kept, requests=plan_prune(entries, repo=repo).requests)`: group 3 lists `src/devops_cli/git/worktree_add.py` in `changes`, so its `plan_prune` call takes the new keyword.
- `prune_worktrees` needs a checkout of the repository, because it runs `git worktree remove`, and a client of GitHub, because it reads the merged pull request of each in-scope tip; the tests give it a real checkout under the test directory and the fake GitHub API.
- `plan_prune` needs a checkout of the repository for the paths and sizes of the worktrees, and makes no request, so it needs no client and no network.
- `count_ignored_paths` needs a checkout of the repository, because it runs `git status --porcelain --ignored` in the worktree; no client and no network.
- `scope_refusal` needs a checkout of the repository through `count_ignored_paths`; no client and no network.
- `managed_folder` needs the settings of the checkout through `load_settings`; no client and no network.
- No new command and no new verify program: each verify is `uv run devops ci test` of a test path or `uv run devops ci docs`, and each failure is the exit status of that row. The runner holds `uv`, `python`, `pytest` and `git` in its image tools, and the plan adds no other program; the pod keeps `readOnlyRootFilesystem` true, so each test writes only under the test directory.
- The first checks that the implementation runs against the real system: `uv run devops ci test tests/git/test_repos_worktrees_reclaim_scope.py`, then `uv run devops ci fail-to-pass --base origin/main`, which names the new scope tests as failing on the base.
- The alternatives verdict of 2026-11-19 is taken from the issue body; the tool facts behind it are not checked in this run. The plan makes no claim about every worktree of a checkout: it changes the decision of each worktree, and no count of them is checked in this run, so the plan names no census.

## Existing Tool Considered

None. The alternatives check of 2026-11-19 records the verdict none: the only tools it found are gtr (git-worktree-runner) and its wrappers gtri and gtr.nvim, they list, create and clean merged worktrees but refuse no ignored path and no foreign folder, and gtr is archived. The change therefore builds its own code: one shared scope function of about 40 lines with tests, at a written cost of about 1,500 tokens to build, keep and fix, and about 30 minutes. It deletes no internal code.

## Dependencies

None.
