# Design

## Decisions

- **Put the shared scope refusal in one public function `scope_refusal(entry, *, managed_root)` in `src/devops_cli/git/worktree_inventory.py`, beside `count_ignored_paths`.**: The module already holds the ignored counter and the prune decision, so one import serves both callers and no new module appears. The reclaim already imports from it.
- **Check the outside folder first, then the ignored paths.**: The order matches the reclaim, so both callers give one reason for one worktree, and a foreign worktree costs no git call.
- **Give the outside reason the managed folder, as `outside the managed folder <folder>`, and the ignored reason the count, as `holds 1 ignored path` or `holds 3 ignored paths`.**: The issue asks the preview to name the folder and the ignored count, and one shared text keeps both callers equal. The singular form matches the existing dirty reason.
- **Rename the three kept reasons from `worktrees_add_kept_outside`, `worktrees_add_kept_ignored` and `worktrees_add_kept_ignored_unknown` to `worktrees_kept_outside`, `worktrees_kept_ignored` and `worktrees_kept_ignored_unknown`, and keep `worktrees_add_kept_line`.**: Prune and the reclaim print these reasons, so the `add` prefix would name one caller only. The line message stays, because it belongs to the shared renderer and a rename would touch a third module for no behavior.
- **Run the scope check after `_decided_by_local_state` and before the merged-pull request read.**: The local-state rule keeps the main worktree, the current directory, a locked worktree and a dirty worktree, and `--force` returns `forced` there, so force keeps its precedence and a refused worktree costs no GitHub request.
- **Pass the resolved managed folder into `_decide`, `plan_prune` and `prune_worktrees` from their callers, and leave `managed_folder` in `src/devops_cli/git/worktree_add.py`.**: `worktree_inventory.py` reads no settings, and `worktree_add.py` imports it, so a move would need a settings read in the decision module or a cycle. Both callers already import `managed_folder`.
- **Refuse in the dry run as well, by giving `plan_prune` the managed folder.**: The preview must list no read for a worktree that the scope keeps, as the local-state rule already does, and the dry run must show the same refusal as the confirm run.
- **Move the worktrees of the prune tests under the managed folder before the prune decision changes, and run that module in the verify of the group that moves it.**: A prune test that builds its worktree under the test directory would be refused after the change and would test nothing. Moving it first keeps every step green, and a verify that runs the module catches a broken fixture.
- **State the scope in the docstring of `worktrees_prune` and in `HELP.repos.worktrees_prune` and `HELP.repos.worktrees_force`, and put the paragraph in section 4 of `CONTRIBUTING.md`.**: The docstring is the help of the command and the section holds the git and worktree rules that a contributor reads. `docs/commands/repos.md` is generated, so the same pull request regenerates it with `uv run devops docs generate`.

## Rejected alternatives

- **Make the scope a method on the worktree record value.**: The rule needs the managed root and a git call for the ignored count, which a value object does not hold: `src/devops_cli/git/worktree_inventory.py:60:` `class WorktreeEntry(BaseModel):` holds the fields of a record, while `src/devops_cli/git/worktree_inventory.py:227:` `def count_ignored_paths(worktree_dir: Path) -> int | None:` runs git in the worktree.
- **Put the scope in a new module `worktree_scope.py`.**: One small function does not justify a module, and the rule belongs beside its owner, `src/devops_cli/git/worktree_inventory.py:417:` `def _decide(`, which is the only prune decision.
- **Check the ignored paths before the folder.**: It changes the reason that a foreign worktree shows and adds a git call for each foreign worktree, while the reclaim checks the folder first at `src/devops_cli/git/worktree_add.py:272:` `if not Path(entry.path).resolve().is_relative_to(folder):`.
- **Make `--force` keep the worktrees that the scope refuses.**: The issue states that `--force` stays the way to remove every worktree, and `src/devops_cli/git/worktree_inventory.py:400:` `if force:` returns `forced` before every other rule.
- **Keep the old reason text `outside the managed folder` with no folder.**: The issue asks the preview to name the folder in the expected behavior, and `src/devops_cli/git/worktree_add.py:272:` `if not Path(entry.path).resolve().is_relative_to(folder):` already holds the folder that a person needs to see.
- **Edit `docs/CLI_REFERENCE.md` by hand.**: The command pages are generated: `README.md:165:` `devops docs generate` writes them from the command tree, and the `docs` row refuses a page that is not the output of its generator.
- **Add a worktree manager library.**: The alternatives check of 2026-11-19 found only gtr and its wrappers, which are archived and decide no scope, and `src/devops_cli/git/worktree_inventory.py:227:` `def count_ignored_paths(worktree_dir: Path) -> int | None:` already wraps git's own plumbing.

## Unchanged references

- `src/devops_cli/commands/repos.py` (message name): The module holds only `worktrees_add_kept_line` at line 708, and that message keeps its name.
