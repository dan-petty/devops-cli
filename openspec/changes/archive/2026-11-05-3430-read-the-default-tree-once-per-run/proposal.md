# Proposal

## Why

The plan check of the implement job (#3393) lists the files of `origin/<default>` for each Planned item that a run judges. The lookup of the base specs lists them once more. The default branch does not change during a run. A run over many Planned items repeats the same `git ls-tree` for each item (#3430).

## What Changes

- `_Judge` in `src/devops_cli/roadmap/implement.py` lists the files of `origin/<default>` once for a run. It gives that list to the plan check of every item. It lists them on the first read, so a run that needs no plan check lists nothing.
- The lookup of the base specs takes that list. The run reads the default tree with one `git ls-tree` and each base spec file with one `git show`.
- `specs_at` in `src/devops_cli/roadmap/plan_read.py` takes the paths of the revision as an optional argument. Its other callers keep the listing that it makes.
- The plan check lists the branch of each Staged item for that item. Each Staged item has its own branch.
- A run returns the same targets and the same left-out reasons as a run that reads the default tree for each item.
- Tests in `tests/roadmap/test_roadmap_implement_job.py` count the git commands of a run at the process edge. They show one listing of the default tree for two Planned items. They show one read of each base spec file and one listing for each Staged branch. They show the same decision for each item as a run that names the item. They show a left-out reason when git cannot list the default tree.
- The page `docs/roadmap/implement.md` says that a run reads the default tree one time.
- The change adds the requirements to the capability `roadmap-implement-job`. The issue states the reads of a run as acceptance criteria, and the process edge shows them.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: the plan check reads the default tree and the base specs once for each run

## Impact

- Code: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`
- Documents: `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_roadmap_implement_job.py`

## Feasibility

- Issue #3393 is on the default branch, so the dependency of the issue is met. The key question of the issue says that the gate does not exist. That text is out of date. `_Judge._plan_reason` in `src/devops_cli/roadmap/implement.py` calls `tree_files`, `change_root`, `files_at`, `read_change` and `check_proposal`.
- The issue names the readers `files_at`, `file_texts_at` and `base_specs_at`. A search of `src/devops_cli/roadmap/plan_read.py` finds `tree_files`, `files_at` and `specs_at`. It finds no `file_texts_at` and no `base_specs_at`. The change uses the real names.
- The run reads the base specs once already: `_Judge._base_facts` is a `cached_property` (#3393). The listing of the default tree is the part that is left. `_plan_reason` calls `tree_files` for each Planned item. `specs_at` calls it once more.
- The test `test_a_run_over_two_planned_items_lists_the_default_tree_once` of this change fails on the base. Two Planned items give 3 listings of `origin/main` (`assert 3 == 1`). The tests for the base spec reads, the Staged listings and the selection pass on the base. They guard behavior that the change must keep.
- The issue says that `plan_implement` reads the default tree and passes it to `_Judge`. The change reads it in `_Judge` on first use. `_plan_reason` catches `GitOperationError` for each item. A read in `plan_implement` would end the run when git fails. The design records this.
- First check: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`. It runs the job with real git on a clone that has an `origin`. It counts the git commands at the process edge.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/test_roadmap_plan_check.py tests/roadmap/test_roadmap_plan_recheck.py`. It shows that the callers of `specs_at` keep their behavior.

## Existing Tool Considered

No open, maintained tool or library covers this need. The repeat is a read of the repository's own git tree inside one function. The change reuses `tree_files`, `files_at` and `specs_at` of `src/devops_cli/roadmap/plan_read.py`. It follows the `cached_property` that `_Judge._base_facts` already uses. Written cost: about 2,000 tokens to build and test, about 500 tokens to keep and fix, and about 1 hour of elapsed time. The change deletes no code.
