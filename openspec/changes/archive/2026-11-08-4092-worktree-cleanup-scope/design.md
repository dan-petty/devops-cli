# Design

## Decisions

- **Filter in `reclaim_merged_worktrees`, before `plan_prune` or `prune_worktrees`.**: The issue limits the change to the `add` reclaim, and `prune_worktrees` and `plan_prune` also serve the `prune` command, which keeps its scope.
- **The managed folder is `managed_folder(repo_root)`, the folder that `worktree_directory` puts `w-<issue>` in, and a worktree is inside when `Path(entry.path).resolve().is_relative_to(folder)`.**: `managed_folder` is the one place that builds the `agent/worktrees` folder, and `_decided_by_local_state` already compares resolved paths with `is_relative_to`. A link or a `..` in a path cannot move a worktree into the folder.
- **An outside worktree becomes a `kept` item with the reason `outside the managed folder`, and no GitHub read is made for it.**: The scope check runs first, so a prunable record outside the folder is kept as well and the dry run lists no read for it.
- **`count_ignored_paths` counts the `!!` entries of `git status --porcelain --ignored -z`, and the reclaim calls it for each worktree under the managed folder. `inventory_worktrees`, `WorktreeEntry` and `_decide` do not change.**: `count_dirty_paths` stays as it is, so `prune` and `status` keep their numbers, and `prune` does not check ignored files. The reclaim keeps a worktree with an ignored path, with a reason that gives the count, before any GitHub read. If `git status` fails, the reclaim keeps the worktree too.
- **`ReclaimResult` and `WorktreeAddReport` get a `kept` list of `WorktreePruneItem` records, and the table output renders each as a `kept <path>: <reason>` line.**: The item shape and the renderer exist. The expected output of the issue names each kept worktree with its reason.
- **The reclaim has no `--force` path.**: `reclaim_merged_worktrees` calls `prune_worktrees` with `confirm=True` and no `force`, and the scope check runs before the local-state decision.
- **The existing reclaim tests move their worktrees under the managed folder, and the shared `repo` fixture moves to `tests/git/conftest.py`.**: The two test files need the same repository, and a conftest fixture needs no import between test modules.
- **The change carries a MODIFIED requirement of `repos-worktrees-add`.**: The command's output and JSON report are observable, so the config asks for a delta, and the requirement `A run reclaims the worktrees of merged work first` exists.

## Rejected alternatives

- **Filter in `prune_worktrees` for every caller.**: It changes `devops repos worktrees prune`, which the issue says keeps its scope (`openspec/specs/repos-worktrees-prune/spec.md` lists its removals).
- **Filter in `_decide` with a global setting.**: `_decide` is a pure decision shared by `plan_prune` and `prune_worktrees`. A setting there couples it to the `add` command.
- **Count ignored files as dirty for every caller.**: `git status --porcelain` and `git status --porcelain --ignored -z` differ in the output of a worktree with only an ignored file (nothing against `!! keep.log`, tested by `test_ignored_file_keeps_worktree`). A change of `count_dirty_paths` would change the numbers of `worktrees status` and `prune`, and it would hide the ignored-file reason in the dirty count.
- **Keep the current clean rule.**: It deletes ignored work: `git worktree remove` without `--force` removes a worktree that holds an ignored file.
- **Put the kept reasons in `reclaim_error`.**: `reclaim_error` means a failed reclaim, and the output prints it as a warning that the worktrees were not reclaimed.
- **Skip outside worktrees without a word.**: The issue asks for the name and the reason of each kept worktree.
