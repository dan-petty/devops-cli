# Proposal

## Why

Issue #3307: the path gate checks that each path a plan names exists, and it never compares the plan with the files that call a function whose signature the plan changes. A person found the missing `stage.py` caller of `check_proposal` in the plan of #3200 by hand, after the stage job had accepted it.

## What Changes

- `path_problems` in `src/devops_cli/roadmap/stage/stage_paths.py` refuses a plan that adds a parameter to a function and leaves out a file under `src/` that calls the function.
- `StagedTree.read` keeps the checkout, and `StagedTree.callers` returns the files of the commit that call a function, found with `git grep`. A tree built from a list of files, as the replay builds it, has no checkout and skips the check.
- A new message in `src/devops_cli/lang/en/messages.py` names the function and the caller file that the plan leaves out.
- New cases in `tests/roadmap/stage/test_roadmap_stage_paths.py` cover the function name, the caller search, a missing caller, a complete caller list and a tree with no checkout.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The path gate names every caller of a function that a task changes

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_paths.py`

## Feasibility

- `src/devops_cli/roadmap/stage/stage_paths.py` holds `class StagedTree` with `read`, which lists the tracked files with `git ls-files`, and `path_problems(groups, tree)`, the place where a caller check belongs.
- `src/devops_cli/roadmap/stage/stage_change.py` holds `def check_proposal`, which calls `path_problems(proposal.groups, tree)`, so the job and the replay read one rule set.
- `src/devops_cli/roadmap/stage/stage.py` builds the tree with `StagedTree.read(checkout, operation=...)`, so the checkout is at hand when the gate runs.
- `src/devops_cli/roadmap/stage/stage_tools.py` holds a `callers` tool that runs `git grep -n -I -E` at a commit, so the grep form is already proven in this code.
- `src/devops_cli/roadmap/stage/stage_eval_cases.py` builds a tree with `StagedTree(files)` and no checkout, which is why the replay must skip the caller check.
- `tests/roadmap/stage/test_roadmap_stage_paths.py` exists and holds the cases of `path_problems`, so the new cases join it.
- The checks against the real system are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` and `uv run devops openspec check`.

## Existing Tool Considered

Git's `git grep` is open and maintained and covers the textual caller search. It lacks the task parsing and the plan comparison. The change builds that check: about 40,000 tokens to build, keep and fix it, and about 8 hours. It deletes no internal code.
