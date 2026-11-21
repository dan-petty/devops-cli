# Tasks

## 1. The plain publish

Kind: behavior.

- [x] 1.1 Write failing tests: a patch in a fixed format that no diff setting changes; a patch up to a commit; two commits of the bot on a base other than the old tip; a new branch only where none is; the new tree read from its objects; a second publish of the same tree with no push; the delete of a branch that `publish` made
  - Verification: `$ uv run devops ci test tests/roadmap/phases`
- [x] 1.2 Write the patch with fixed format flags, apply the patches with `git apply --index` in a new repository, clone the issue branch plainly in `prepare` (`phases/checkout.py`), and move fix-checks onto them with no URL carry and no `--source`
  - Verification: `$ uv run devops ci test tests/roadmap/phases tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py tests/commands/test_roadmap_step_fix_checks.py`

## 2. implement on the phases

Kind: behavior.

- [x] 2.1 Write failing tests: the phases in separate calls reach the draft, and the agent phase makes no GitHub call; a second `publish` pushes and comments nothing; `publish` masks each text of the outcome; a state that names another branch; `prepare` starts git only; the skip rule of the rebase; each phase of the command makes its process unreadable first; the contract of the agent phase in the prompt
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phases.py tests/commands/test_roadmap_implement_phases.py tests/roadmap/implement/test_roadmap_implement_prompt.py`
- [x] 2.2 Split the run into `prepare`, `agent` and `publish` (`implement_phases.py`, `implement_report.py`), settle the stops of the rebase in the agent, delete the checkpoints, the withdraw, the rebase before each push and `implement.base`, and add `--phase` and `--work` to `devops roadmap implement`
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/core/test_roadmap_implement_planned_run.py tests/roadmap/test_roadmap_faults.py tests/telemetry/test_roadmap_intake_implement_metrics.py`

## 3. Documents

Kind: other.

- [x] 3.1 Add the addendum of the plain flow to ADR 0030, state the phases in the docstring of `implement_run.py`, `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md` and `CONTEXT.md`, and regenerate the documentation
  - Verification: `$ uv run devops ci docs`
