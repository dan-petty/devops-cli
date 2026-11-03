# Proposal

## Why

`src/devops_cli/roadmap/` is one flat package of 63 files (#3187). The job modules show only as name prefixes (`refine*`, `stage*`, `implement*`, `intake*`) beside the store modules, so a reader cannot see which files belong to one job, and a change to one job touches files that sit among the files of the others. The five largest modules hold between 1,304 and 2,438 lines each.

## What Changes

- Move each job module of `src/devops_cli/roadmap/` into `intake/`, `refine/`, `stage/` or `implement/` with `git mv`, with no edit to its body.
- Move `store.py`, `github_store.py` and `memory_store.py` into `src/devops_cli/roadmap/stores/`.
- Rewrite every import of a moved module in `src/` and in `tests/` to its new module path.
- Add invariant tests that hold the subpackages, the store folder, the import paths and the docstring-only package module.
- Move the roadmap test modules into the mirror directories of `tests/roadmap/`.
- Document the new layout in `docs/roadmap/README.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-package-layout`: Each roadmap job has its own subpackage, The store modules sit under stores, Every caller imports a roadmap module by its path, The roadmap package module exports no name

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/stores/__init__.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/stores/memory_store.py`, `src/devops_cli/roadmap/intake/__init__.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/intake/intake_model.py`, `src/devops_cli/roadmap/intake/intake_requests.py`, `src/devops_cli/roadmap/refine/__init__.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/__init__.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/implement/__init__.py`, `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/claim.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/github/issues.py`, `src/devops_cli/survey/intake.py`, `src/devops_cli/ai/research/mental_model.py`
- Documents: `docs/roadmap/README.md`
- Tests: `tests/invariants/test_source_tree.py`, `tests/roadmap/intake/test_roadmap_intake.py`, `tests/roadmap/refine/test_roadmap_refine.py`, `tests/roadmap/stage/test_roadmap_stage_job.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/stores/test_roadmap_github_store.py`, `tests/support/roadmap.py`

## Feasibility

- The issue cites `refine.py`, `intake.py`, `stage.py`, `implement_step.py` and `run.py` without a directory. The probes report each bare name as no file of the commit and that no commit deleted or renamed it, so the modules live at their full paths under `src/devops_cli/roadmap/`, which the tool calls below confirm. No cited path is missing.
- `list_files src/devops_cli/roadmap` shows one flat folder: `intake.py`, `intake_model.py`, `intake_requests.py`, `refine.py`, `refine_investigation.py`, `stage.py`, `stage_change.py`, `stage_criteria.py`, `stage_probe.py`, `stage_tools.py`, `implement.py`, `implement_step.py`, `run.py`, `store.py`, `github_store.py`, `memory_store.py` and the other job modules sit together, and no subpackage holds any of them. The premise of #3187 holds.
- `list_files tests/roadmap` shows the roadmap test modules flat in `tests/roadmap/`, so the mirror of the new tree is work of this change.
- `read_file src/devops_cli/roadmap/__init__.py` shows a docstring and no import, so the package re-exports no name and each caller imports a submodule (`from devops_cli.roadmap import store as roadmap_store` in `src/devops_cli/commands/roadmap.py`).
- First checks against the real system, in order: `git mv` one module and `git log --follow --oneline -- src/devops_cli/roadmap/refine/refine.py` to see the history follow it, then `uv run devops ci test tests/roadmap`, then `uv run devops ci` for the full gate, then `uv run devops openspec check`.

## Existing Tool Considered

`git mv` records each move as a rename so `git log --follow` keeps the history, and `ruff` (`ruff check --select I --fix`) rewrites the import lines of a moved module. No open tool decides the grouping: that is a person's judgement, which this plan records. The written cost is about 120k tokens and 6 hours of work, and nothing to keep afterwards, because the grouping is data in the tree and no new code runs. The change deletes no internal code: it moves modules and rewrites imports, and the only lines it removes are the old import lines of the callers.
