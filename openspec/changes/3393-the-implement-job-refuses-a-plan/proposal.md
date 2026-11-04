# Proposal

## Why

The implement job takes a Staged or Planned item without reading its plan content. PR #3335 is a Staged plan for #3321 with `x` in every text, opened before the content gate merged: `devops roadmap implement --item 3321` parses `tasks.md`, takes the group that changes `src/devops_cli/roadmap/stage_change.py`, and spends a model call on the task `1.1 x` before it stops. #3387 covers the stage side only, so a plan that the current gate refuses still starts a runner Job (#3393).

## What Changes

- `_Judge.judge` in `src/devops_cli/roadmap/implement.py` runs the plan check on the plan of an item before it returns a target.
- A reader in `src/devops_cli/roadmap/implement.py` builds a `StageProposal` from the change folder of a Staged branch or of the default branch and hands it to `check_proposal` with the base capability names, the requirement names, the item body and the tree.
- An item whose plan returns problems is left out with the first problem as its reason, so `devops roadmap explain` and the implement report show it.
- Tests in `tests/roadmap/test_roadmap_implement_job.py` cover a plan with a placeholder task and a plan that passes the check.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job leaves out an item whose plan fails the check

## Impact

- Code: `src/devops_cli/roadmap/implement.py`
- Documents: `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_roadmap_implement_job.py`

## Feasibility

- The probes confirm that the cited code exists at the commit: "The path `src/devops_cli/roadmap/implement.py` is a file of the staging commit."
- The probes confirm the gate module and its tests: "The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit." and "The path `tests/roadmap/test_roadmap_implement_job.py` is a file of the staging commit."
- The probes confirm the other two cited modules: "The path `src/devops_cli/roadmap/implement_run.py` is a file of the staging commit." and "The path `src/devops_cli/roadmap/planned.py` is a file of the staging commit."
- read_file src/devops_cli/roadmap/implement.py showed `_Judge.judge` returning `ImplementTarget | str` and the module docstring saying that the module "selects and plans. It makes no write to git or to GitHub."
- read_file src/devops_cli/roadmap/stage_change.py showed `def check_proposal(proposal: StageProposal, known: Collection[str], tree: StagedTree, *, requirements=None, issue_body="", probes=()) -> list[str]`, so the gate takes the proposal, the capability names, the tree and the item body.
- read_file src/devops_cli/roadmap/planned.py showed `PlannedChanges` with the `active` and `archived` folders and `tasks_on_default(source, planned, folder, operation=...)`, so the change folder of a Planned item is known before a branch exists.
- First check: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`, which runs the new failing tests against the real job and a real clone with an origin.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py`, which holds the existing `check_proposal` cases and shows the gate text did not change.
- Third check: `uv run devops openspec check`, which shows the change folder of this item passes the same validation.

## Existing Tool Considered

check_proposal and its gates already exist in `src/devops_cli/roadmap/stage_change.py`, and `src/devops_cli/roadmap/planned.py` already reads `tasks.md` of a Planned item from the default branch. The change calls the existing check and adds one reader for the change folder. Written cost of the reader and the wiring: about 20k tokens to build, keep and fix, and 1 hour of elapsed time. The change deletes no code.
