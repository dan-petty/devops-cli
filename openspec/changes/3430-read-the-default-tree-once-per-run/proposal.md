# Proposal

## Why

The plan check of the implement job (#3393) lists the files of `origin/<default>` for each Planned item that a run judges, and the lookup of the base specs lists them once more. The default branch does not change during a run, so a run over many Planned items repeats the same `git ls-tree` for each item (#3430).

## What Changes

- `_Judge` in `src/devops_cli/roadmap/implement.py` lists the files of `origin/<default>` once for a run and gives that list to the plan check of every item. The judge lists them on the first read, so a run that needs no plan check lists nothing.
- The lookup of the base specs takes that list, so the run reads the default tree with one `git ls-tree` and each base spec file with one `git show`.
- `specs_at` in `src/devops_cli/roadmap/plan_read.py` takes the paths of the revision as an optional argument. Its other callers keep the listing that it makes.
- The plan check lists the branch of each Staged item for that item, because each Staged item has its own branch.
- A run returns the same targets and the same left-out reasons as a run that reads the default tree for each item.
- Tests in `tests/roadmap/test_roadmap_implement_job.py` count the git commands of a run at the process edge: one listing of the default tree for two Planned items, one read of each base spec file, one listing for each Staged branch, the same decision for each item as a run that names the item, and a left-out reason when git cannot list the default tree.
- The page `docs/roadmap/implement.md` says that a run reads the default tree one time.
- The change adds the requirements to the capability `roadmap-implement-job`, because the reads of a run are observable at the process edge and the issue states them as acceptance criteria.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The plan check lists the default tree once for each run, It reads the base specs once for each run, It lists the branch of each Staged item, The reads of one run give the same selection as a read for each item, A default tree that git cannot list leaves the items out

## Impact

- Code: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`
- Documents: `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_roadmap_implement_job.py`

## Feasibility

- #3393 is on the default branch (pull requests #3615 and #3626), so the dependency of the issue is met. The key question of the issue says that the gate does not exist, and that text is out of date. `_Judge._plan_reason` in `src/devops_cli/roadmap/implement.py` calls `tree_files`, `change_root`, `files_at`, `read_change` and `check_proposal`.
- The issue names the readers `files_at`, `file_texts_at` and `base_specs_at`. A search of `src/devops_cli/roadmap/plan_read.py` finds `tree_files`, `files_at` and `specs_at`, and finds no `file_texts_at` and no `base_specs_at`. The change uses the real names.
- The base specs are read once for each run already: `_Judge._base_facts` is a `cached_property` (#3393). The part of the issue that is left is the listing of the default tree. `_plan_reason` calls `tree_files` for each Planned item, and `specs_at` calls it once more.
- The test `test_a_run_over_two_planned_items_lists_the_default_tree_once` of this change fails on the base: two Planned items give 3 listings of `origin/main` (`assert 3 == 1`). The tests that count the base spec reads, the Staged listings and the selection pass on the base, so they guard behavior that the change must keep.
- The issue says that `plan_implement` reads the default tree and passes it to `_Judge`. The change reads it in `_Judge` on first use. `_plan_reason` catches `GitOperationError` for each item, and a read in `plan_implement` would end the run when git fails. The design records this.
- First check: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`, which runs the job and counts the git commands at the process edge, with git real on a clone that has an `origin`.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/test_roadmap_plan_recheck.py`, which shows that the callers of `specs_at` keep their behavior.

## Existing Tool Considered

No open, maintained tool or library covers this need: the repeat is a read of the repository's own git tree inside one function. The change reuses `tree_files`, `files_at` and `specs_at` of `src/devops_cli/roadmap/plan_read.py`, and follows the `cached_property` that `_Judge._base_facts` already uses. Written cost: about 2,000 tokens to build and test, about 500 tokens to keep and fix, and about 1 hour of elapsed time. The change deletes no code.
