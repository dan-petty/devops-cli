# Proposal

## Why

The implement job takes a Staged or Planned item without reading its plan content. PR #3335 was a Staged plan for #3321 with `x` in every text at commit 837e157e, opened before the content gate merged: `devops roadmap implement --item 3321` parsed `tasks.md`, took the group that changes `src/devops_cli/roadmap/stage_change.py`, and spent a model call on the task `1.1 x` before it stopped. #3387 covers the stage side only, so a plan that the current gate refuses still starts a runner Job (#3393).

## What Changes

- `_Judge.judge` in `src/devops_cli/roadmap/implement.py` runs the plan gate on the plan of an item before it returns a target, so a refused plan makes no branch and no runner Job.
- The job reads the change folder at the revision that holds the plan: `origin/<branch>` for a Staged item and `origin/<default>` for a Planned item. It reuses `tree_files`, `files_at`, `change_root`, `specs_at` and `read_change` of `src/devops_cli/roadmap/plan_read.py`, so the implement job and the plan-check command read a plan with one reader.
- The job calls the existing `check_proposal` with the base capability names and requirement names at `origin/<default>`, the item body and a `StagedTree` of the revision.
- An item whose plan returns problems is left out with the first problem as its reason, so `devops roadmap explain` and the implement report show it. An item whose plan the reader or git cannot read is left out with that reason and does not stop the other items.
- Tests in `tests/roadmap/test_roadmap_implement_job.py` cover a placeholder task at a staged branch, a placeholder at the default branch, a plan that passes, a plan that the reader refuses, a plan with two problems, and a test path that no file holds.
- The check refuses a plan before the run, so the job starts no run that amends a missing test path or a refused command. The six job tests of those amendments in `tests/roadmap/test_roadmap_implement_amend_job.py` are removed, and the scenarios of `roadmap-implement-job` that describe those amendments are modified to match.
- The fixtures of the fail-to-pass tests (`tests/support/base_replay.py` and `tests/roadmap/test_roadmap_implement_job.py`) are plans that the reader accepts: each group names its `Reads:` and `Changes:` lines, each task is numbered, and the plan holds a criteria entry.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job leaves out an item whose plan fails the check

## Impact

- Code: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_plan_read.py`, `tests/support/roadmap_implement.py` (the test world holds a plan that the gates accept)

## Feasibility

- read_file `src/devops_cli/roadmap/plan_read.py` showed `def read_change(files: Mapping[str, str]) -> StageProposal`, so the change calls one existing reader and adds no reader.
- read_file `src/devops_cli/roadmap/plan_check.py` showed that `plan_check` lists the head files with `git ls-tree`, reads them with `git show`, finds the change folder with `_change_root`, and calls `read_change` and `check_proposal`. The change makes those revision reads public in `plan_read.py` and calls them from both jobs.
- read_file `src/devops_cli/roadmap/stage_change.py` showed `def check_proposal(proposal: StageProposal, known: Collection[str], tree: StagedTree, *, requirements=None, issue_body="", probes=(), overlaps=()) -> list[str]`.
- read_file `src/devops_cli/roadmap/implement.py` showed `_Judge.judge` returning `ImplementTarget | str` and the module docstring saying that the module "selects and plans. It makes no write to git or to GitHub."
- read_file `src/devops_cli/roadmap/planned.py` showed `PlannedChanges.default` and `tasks_on_default`, so the default branch of a Planned item is known before a branch exists.
- `devops pr view 3335` and `git show 837e157e` confirm the premise: PR #3335 was a plan pull request for #3321 and commit 837e157e holds the placeholder plan.
- The premise holds at `origin/main` 502219a4. `_Judge.judge` in `src/devops_cli/roadmap/implement.py` and `_planned_target` run no plan gate. A probe that ran `read_change` and `check_proposal` on the tree of commit 837e157e returned 9 problems, the first of which is "The text of why has 1 characters, and the least is 10." The stage job runs the same gate (`stage.py`).
- First check: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py`, which runs the new failing tests against the real job and a real clone with an origin.
- Second check: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py tests/roadmap/test_roadmap_plan_check.py`, which shows the shared readers keep the plan-check behavior.
- Third check: `uv run devops openspec check`, which shows the change folder of this item passes the same validation.

## Existing Tool Considered

`read_change` in `src/devops_cli/roadmap/plan_read.py` reverses `render_change` and returns the `StageProposal` that `check_proposal` takes. The `plan_check` command already reads a change folder at a revision and runs that gate. `StagedTree`, `read_spec` and `read_base_specs` cover the tree and the base specs. The change moves the revision readers of `plan_check` to `plan_read` and calls them from the implement job. It writes no second reader and no second rule set. Written cost: about 20k tokens to build, keep and fix, and 1 hour of elapsed time. The change deletes no code and no behavior. It moves four helpers from `plan_check.py` to `plan_read.py`.
