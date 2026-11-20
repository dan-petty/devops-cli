# Proposal

## Why

`devops repos worktrees prune --confirm` removes each clean worktree whose tip heads a merged pull request, in any folder. `git worktree remove` also deletes the files that `.gitignore` hides. So prune can delete agent scratch files, a local `.env` or other ignored data, and it can remove the worktrees that other tools made outside the repository (#6435). The issue does not know whether the worktrees that prune removed on 2026-11-19 held such files.

The reclaim of `devops repos worktrees add` (#4092) already keeps a worktree outside the managed folder and a worktree that holds ignored paths, but prune does not ask that rule. The reclaim rule has a second problem: it counts every ignored path. Each used worktree holds caches that a command makes again, such as `.venv` and `__pycache__`, so the rule keeps almost every used worktree, and only `--force` frees the disk.

This change gives prune and the reclaim one shared scope rule. The rule keeps a worktree outside the managed folder, also a record whose directory is missing. It keeps a worktree that holds ignored data files: the ignored files that are not regenerable caches or build outputs. The help text and `CONTRIBUTING.md` state the rule.

## What Changes

- Add `CONST_WORKTREE_REGENERABLE_PATHSPECS` to `src/devops_cli/config/constants.py`: the git exclude pathspecs of the regenerable paths of a worktree. No existing constant has this meaning: `CONST_SEMGREP_EXCLUDED_DIRECTORIES` and the cache lists of `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/security/prompt_injection.py` and `src/devops_cli/roadmap/stage/stage_removal_references.py` hold `.data` or `.git`, which hold data.
- Replace `count_ignored_paths` in `src/devops_cli/git/worktree_inventory.py` with `count_ignored_data_files`. It runs `git ls-files --others --ignored --exclude-standard -z` with the regenerable pathspecs excluded, so it counts each ignored file, also inside `.data/`, but no cache file and no empty directory. Delete `CONST_GIT_IGNORED_PREFIX`, which only the old counter used.
- Add `scope_refusal(entry, *, managed_root)` to `src/devops_cli/git/worktree_inventory.py`. It returns the reason that keeps a worktree out of a removal, or None. It checks the folder first, then the ignored data files.
- Call `scope_refusal` in `_split_by_scope` of `src/devops_cli/git/worktree_add.py` in place of its two inline checks.
- Rename the three kept reasons of `src/devops_cli/lang/en/messages.py` to `worktrees_kept_outside`, `worktrees_kept_data` and `worktrees_kept_data_unknown`. The outside reason names the managed folder. The data reason gives the count in the singular or plural form.
- Give `_decided_by_local_state`, `_decide`, `plan_prune` and `prune_worktrees` a required keyword-only `managed_root`. Prune asks `scope_refusal` after the main worktree, the current directory and `--force`, and before the lock, the missing directory, the dirty state and the merged pull request. So a refused worktree costs no GitHub request, also in the dry run.
- Pass the managed folder from each caller in the same task group: `worktrees_prune` of `src/devops_cli/commands/repos.py`, `reclaim_merged_worktrees` of `src/devops_cli/git/worktree_add.py`, and the direct call in `tests/git/test_repos_worktrees_reclaim.py`.
- Move the worktrees of the prune tests of `tests/git/test_repos_worktrees.py` under the managed folder first, because prune refuses a worktree outside it after the change.
- State the scope in the docstring of `worktrees_prune`, which is the help of the command, in `HELP.repos.worktrees_force`, and in section 5 of `CONTRIBUTING.md`. Delete `HELP.repos.worktrees_prune`, which no code reads. Regenerate `docs/commands/repos.md`.
- The change is observable: prune refuses more worktrees, the reclaim takes more worktrees, and the reasons change. So the change has spec deltas for `repos-worktrees-prune` and `repos-worktrees-add`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-worktrees-prune`: Ignored data files keep a worktree, Regenerable paths hold no data, A worktree outside the managed folder stays, Prune and the reclaim share one scope rule, Force removes a worktree that the scope refuses, The prune help states the scope, A merged pull request makes a worktree removable
- `repos-worktrees-add`: A reclaim keeps a worktree that it does not manage

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/git/worktree_inventory.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/commands/repos.md`, `CONTRIBUTING.md`
- Tests: `tests/git/test_repos_worktrees.py`, `tests/git/test_repos_worktrees_reclaim_scope.py`, `tests/git/test_repos_worktrees_reclaim.py`, `tests/commands/test_repos.py`
- Open pull request #6479 (#6340) changes other functions of `src/devops_cli/git/worktree_add.py`, `src/devops_cli/commands/repos.py` and `tests/git/test_repos_worktrees_reclaim.py`: `PreReadOrigin`, `_run` and `worktrees_add`. This change edits `_split_by_scope`, `reclaim_merged_worktrees`, `worktrees_prune` and one test call, so the two do not overlap.

## Feasibility

- `git show origin/main:src/devops_cli/git/worktree_inventory.py` at `90d2c041b` (2026-11-20) shows that prune asks no scope rule. `src/devops_cli/git/worktree_inventory.py:425:` `local = _decided_by_local_state(entry, force=force, current_dir=current_dir)` reads only main, current directory, `--force`, lock, missing directory and dirty state, and `src/devops_cli/git/worktree_inventory.py:405:` `if entry.prunable:` returns removable for a missing directory in any folder.
- The same file shows that the counter counts every ignored entry: `src/devops_cli/git/worktree_inventory.py:249:` `return sum(1 for token in raw.split("\0") if token.startswith(CONST_GIT_IGNORED_PREFIX))`.
- `src/devops_cli/git/worktree_add.py:272:` `if not Path(entry.path).resolve().is_relative_to(folder):` and `src/devops_cli/git/worktree_add.py:274:` `elif (ignored := count_ignored_paths(Path(entry.path))) is None:` are the two inline checks of the reclaim. They run before the prune decision, so the reclaim keeps an outside record whose directory is missing.
- The callers of the changed signatures: `src/devops_cli/commands/repos.py:971:` `report = plan_prune(entries, repo=origin, force=force)`, `src/devops_cli/commands/repos.py:973:` `report = prune_worktrees(root, entries, repo=origin, force=force, confirm=confirm)`, `src/devops_cli/git/worktree_add.py:301:` `return ReclaimResult(kept=kept, requests=plan_prune(entries, repo=repo).requests)`, `src/devops_cli/git/worktree_add.py:303:` `report = prune_worktrees(repo_root, entries, repo=repo, confirm=True)` and `tests/git/test_repos_worktrees_reclaim.py:277:` `report = prune_worktrees(repo, entries, repo="example-org/app", confirm=True)`. `git grep` finds no other caller.
- `uv run devops repos worktrees add 6435 --dry-run --type fix --slug worktrees-prune-deletes-ignored-and-foreign` on 2026-11-20 listed 53 kept worktrees of this repository: 35 "outside the managed folder" (under `<home>/.gemini/...`, `<home>/.local/share/kilo/...`, `/tmp/...`, `.claude/worktrees` and `.data/agent/scratch`) and 18 under `.data/agent/worktrees` with "has ignored files" and counts from 1 to 163. So today the reclaim takes no used worktree.
- A measure on 2026-11-20 in the 27 worktrees of this repository under `.data/agent/worktrees` (19) and `<home>/.gemini/antigravity/worktrees/devops-cli` (8) compared the two git calls (git 2.55.0 of the devcontainer, read only). `git status --porcelain --ignored -z` listed 1 to 165 ignored entries in each worktree and took 0.12 to 0.69 s. `git ls-files --others --ignored --exclude-standard -z` with the regenerable pathspecs excluded took 0.21 to 1.05 s, about 1.3 times as long. It listed 0 data files in 14 worktrees, 1 to 6 in 10 worktrees (`.data/agent/scratch`, `.code-workspace`, `.data/junit.xml`), 386 in one (`.data/agent/scratch`), 14353 in one (`mutants`, `.data/agent/scratch`) and 49011 in one (`.data/camp`). The call lists the files inside `.data/` one by one.
- In a scratch repository, the call with the exclude pathspecs listed only `.data/agent/scratch/note.md` and `.env.local` of a worktree that also held `.venv/x`, `src/pkg/__pycache__/m.pyc`, `.pytest_cache/v`, `.data/cache/x`, `.coverage`, `.data/.coverage.1` and an empty `.data/empty`. It exited 0, and it exited 128 when the `.git` file of the worktree was broken, so `None` keeps its meaning: the count is unknown.
- `pyproject.toml` writes the coverage outputs under `.data/`: `data_file = ".data/.coverage"`, `output = ".data/coverage.xml"`, `directory = ".data/htmlcov"` and `output = ".data/coverage.json"`. A coverage run makes them again, so they are regenerable.
- `managed_folder` (`src/devops_cli/git/worktree_add.py:106:` `def managed_folder(repo_root: Path) -> Path:`) gives the folder from the settings. `tests/git/conftest.py:31:` `def managed(isolate_data_dir: Path) -> Path:` gives the tests the same folder.
- `count_ignored_data_files`, `scope_refusal` and `plan_prune` need a checkout and git only; `prune_worktrees` also needs the GitHub client for the merged pull request of each in-scope tip. The tests use real repositories under `tmp_path` and the GitHub fake, as the tests of `tests/git/` do.

## Existing Tool Considered

None. The alternatives check of 2026-11-19 records the verdict none: the only tools it found are gtr (git-worktree-runner) and its wrappers gtri and gtr.nvim. They list, create and clean merged worktrees, but they refuse no ignored file and no foreign folder, and gtr is archived. Git's own plumbing does the count: `git ls-files --others --ignored --exclude-standard` with exclude pathspecs, in place of a file walk of our own. The change builds one shared scope function and one constant, about 60 lines with tests. The written cost is about 2,000 tokens to build, keep and fix that code, and about 45 minutes. It deletes `count_ignored_paths`, `CONST_GIT_IGNORED_PREFIX` and the two inline scope checks of `_split_by_scope`.

## Dependencies

None.
