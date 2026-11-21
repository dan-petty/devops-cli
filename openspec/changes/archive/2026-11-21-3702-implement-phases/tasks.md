# Tasks

## 1. implement on the phases

Kind: behavior.

- [x] 1.1 Write failing tests: the phases in separate calls reach the draft, and the agent phase makes no GitHub call; a second `publish` pushes and comments nothing; `publish` masks each text of the outcome; a state that names another branch; `prepare` starts git only; the skip rule of the rebase; the outputs in a new folder; each phase of the command makes its process unreadable first; the contract of the agent phase in the prompt
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_phases.py tests/commands/test_roadmap_implement_phases.py tests/roadmap/implement/test_roadmap_implement_prompt.py`
- [x] 1.2 Split the run into `prepare`, `agent` and `publish` (`implement_phases.py`, `implement_report.py`), settle the stops of the rebase in the agent, delete the checkpoints, the withdraw, the rebase before each push and `implement.base`, and add `--phase` and `--work` to `devops roadmap implement`
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/core/test_roadmap_implement_planned_run.py tests/roadmap/test_roadmap_faults.py tests/telemetry/test_roadmap_intake_implement_metrics.py`

## 2. Documents

Kind: other.

- [x] 2.1 Add the addendum of the plain flow to ADR 0030, state the phases in the docstring of `implement_run.py`, `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md` and `CONTEXT.md`, and regenerate the documentation
  - Verification: `$ uv run devops ci docs`
