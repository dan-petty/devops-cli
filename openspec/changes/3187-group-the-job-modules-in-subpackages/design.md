# Design

## Decisions

- **Move every module whose name starts with a job prefix, not only the five entry modules.**: The issue forbids a top-level module name that starts with `intake`, `refine`, `stage` or `implement`. A move of `intake.py`, `refine.py`, `stage.py`, `implement.py` and `implement_step.py` alone leaves 32 job modules at the top level. The change moves all 47 job modules: 3 intake, 2 refine, 22 stage and 20 implement.
- **One subpackage for each job, and one `stores/` for `store.py` and `github_store.py`.**: The module prefixes already name the jobs, and the two store modules share one role: the store interface and the GitHub adapter.
- **Move each module whole, with no split of a module over 1,000 lines in this change.**: The issue forbids a split for size alone. A whole move keeps the diff a set of renames and keeps the merge conflict small, and a module splits later when it shows two independent public parts.
- **Move each file with `git mv`.**: Git records a rename, so `git log --follow` keeps the history of the module. A copy and a delete would show a new file and a deleted file.
- **Rewrite the import of each caller to the new module path, and keep no re-export in `devops_cli.roadmap.__init__`.**: `src/devops_cli/roadmap/__init__.py` holds only a docstring, so the package exports no name and every caller imports a submodule. A re-export would add an export layer the package does not have and leave two paths for one module.
- **Rewrite the string targets that name a moved module.**: 69 string targets in the tests name a module, such as `devops_cli.roadmap.implement_run`. A string does not follow an import, and a missed target fails a test or a logger check.
- **Update the package docstring to the new store path.**: The docstring names `devops_cli.roadmap.store.get_roadmap_store`, which the move relocates. A stale path misleads the reader that the docstring serves.
- **Hold the new layout with invariant tests in `tests/invariants/test_source_tree.py`, the file that holds the checks of the source tree.**: `docs/TESTING.md` puts a check of committed files in the subject's file under `tests/invariants/`, and these tests read the tree instead of running a job, so they run offline with no fake.
- **Mirror the new layout in `tests/roadmap/`, one directory for each new subpackage.**: `docs/TESTING.md` sets `tests/` to mirror the package tree of `src/devops_cli` at full depth, and the archived change `2026-10-31-1313-tests-mirror-source-tree` moved the test tree to that layout. A test module that is named for a job behavior moves to that job's directory, and a test of a top-level module stays at `tests/roadmap/`.
- **Move the snapshot file of a moved test module with it.**: syrupy keys a snapshot file by the path of the test module. A test module that moves without its `.ambr` file loses its snapshot.

## Rejected alternatives

- **Keep the flat `src/devops_cli/roadmap/` package and add no subpackage.**: `src/devops_cli/roadmap/` holds 79 modules in one folder, and the job modules show only as name prefixes, which is the problem #3187 states.
- **Move only the five entry modules.**: 32 job modules would still start with a job prefix at the top level, so the layout test of this change would fail and the reader would still not see the job boundary.
- **Group the modules by layer, such as models, jobs and adapters.**: The issue groups by job, and the module names already carry the job: `refine.py`, `refine_investigation.py`, `intake.py`, `intake_model.py`, `stage.py`, `stage_change.py`, `implement_step.py`.
- **Split every module over 1,000 lines while moving it.**: The issue says to split a file over 1,000 lines only where it has two clear parts, and never for its size alone; a split inside the move would hide the rename in the diff.
- **Re-export the moved modules from `devops_cli.roadmap.__init__` so the callers stay unchanged.**: `src/devops_cli/roadmap/__init__.py` holds only a docstring and no import, and the callers import submodules (`from devops_cli.roadmap import store as roadmap_store` in `src/devops_cli/commands/roadmap.py`), so a re-export would add an export layer the package never had.
- **Rewrite the imports with `ruff` alone and leave the string targets.**: `ruff` rewrites an import statement, not a string, so the 69 string targets would keep the old path and fail at run time.
- **Copy each module to its new path and delete the old one.**: Git would see a new file and a deleted file, and `git log --follow` would not keep the history, which the issue asks the move to keep.
