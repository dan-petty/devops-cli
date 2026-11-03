# Proposal

## Why

`src/devops_cli/roadmap/` is one flat package of 79 Python modules (#3187). The job modules show only as name prefixes (`intake*`, `refine*`, `stage*`, `implement*`) beside the store modules, so a reader cannot see which files belong to one job, and a change to one job touches files that sit among the files of the others. The five largest modules hold between 1,390 and 2,459 lines each.

## What Changes

- Move all 47 modules whose name starts with `intake`, `refine`, `stage` or `implement` into `intake/`, `refine/`, `stage/` or `implement/` with `git mv`, with no edit to the body of a moved module.
- Move `store.py`, `github_store.py` and `memory_store.py` into `src/devops_cli/roadmap/stores/`.
- Add a subpackage `__init__.py` with a one-line docstring and no import. Update the module docstring of `src/devops_cli/roadmap/__init__.py` to name the new store path.
- Rewrite every import of a moved module in `src/` and in `tests/` to its new module path. Rewrite the string targets of the tests, such as a `monkeypatch.setattr` path and a logger name, because a string does not follow an import.
- Add invariant tests that hold the subpackages, the store folder, the import paths and the docstring-only package module.
- Move each test module of `tests/roadmap/` whose name starts with a job prefix into `tests/roadmap/<job>/`, and the two store tests into `tests/roadmap/stores/`, with the snapshot files of a moved test module. A test of a top-level module stays at `tests/roadmap/`.
- Document the new layout in `docs/roadmap/README.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-package-layout`: one subpackage for each job and one for the stores, every caller imports a roadmap module by its path, the package module exports no name, the test tree mirrors the subpackages, and history and behavior stay.

### Modified Capabilities

None.

## Impact

- Code: the 50 moved modules under `src/devops_cli/roadmap/`, the subpackage `__init__.py` files, and every module of `src/` that imports a moved module. The main callers are `src/devops_cli/commands/roadmap.py`, `src/devops_cli/github/issues.py`, `src/devops_cli/survey/intake.py` and `src/devops_cli/ai/research/mental_model.py`.
- Documents: `docs/roadmap/README.md`.
- Tests: `tests/invariants/test_source_tree.py`, the roadmap test modules under `tests/roadmap/`, `tests/support/roadmap.py` and the other modules of `tests/support/` that import a moved module.

## Feasibility

- `find src/devops_cli/roadmap -maxdepth 1 -name '*.py' | wc -l` gives the one flat folder of 79 modules, and `ls src/devops_cli/roadmap | grep -E '^(intake|refine|stage|implement)' | wc -l` gives the 47 job modules. No subpackage holds any of them. The premise of #3187 holds.
- `find tests/roadmap -maxdepth 1 -name 'test_*.py' | wc -l` gives 114 test modules flat in `tests/roadmap/`, so the mirror of the new tree is work of this change.
- `cat src/devops_cli/roadmap/__init__.py` shows a docstring and no import, so the package re-exports no name and each caller imports a submodule (`from devops_cli.roadmap import store as roadmap_store` in `src/devops_cli/commands/roadmap.py`). The docstring names `devops_cli.roadmap.store`, so the move updates that line.
- `grep -rn 'devops_cli\.roadmap\.' src tests --include='*.py'` finds 69 string targets in the tests that name a moved module, such as `devops_cli.roadmap.implement_run`; an import rewrite alone does not update them.
- First checks against the real system, in order: `git mv` one module and `git log --follow --oneline -- src/devops_cli/roadmap/refine/refine.py` to see the history follow it, then `uv run devops ci test tests/roadmap`, then `uv run devops ci` for the full gate, then `uv run devops openspec check`.
- The issue blocks the move on the open pull requests #3182 and on the plans for #3011, #3015, #3017 and #3019. This change holds the plan and starts the move only after those pull requests merge.

## Existing Tool Considered

`git mv` records each move as a rename so `git log --follow` keeps the history. `ruff check --select I --fix` rewrites the import lines of a moved module. Neither tool rewrites a string target or a logger name, so a `git grep` check holds those. No open tool decides the grouping: that is a person's judgement, which this plan records. The written cost is about 120k tokens and 6 hours of work, and nothing to keep afterwards, because the grouping is data in the tree and no new code runs. The change deletes no internal code: it moves modules and rewrites imports, and the only lines it removes are the old import lines of the callers.
