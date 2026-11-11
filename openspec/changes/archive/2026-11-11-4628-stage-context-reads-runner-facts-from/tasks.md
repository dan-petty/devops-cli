# Tasks

## 1. Behavior: the runner facts come from the installed modules

- [x] 1.1 Add the failing tests: a retry text and a `uv` text get their sections when no staged read returns a file, the Dockerfile of another repository gives no image facts, each `NOT_IN_RUNNER` line holds its reason text, the 3 staged fact files exist, a case whose commit and checkout lack the module files reaches the model, and the job reaches the model for such a commit
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_context.py tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py`
- [x] 1.2 Read `FailureClass`, `ACTION_BY_CLASS`, `tool_names()` and `NOT_IN_RUNNER` from the installed modules, read the Dockerfile packages and the pod security settings only for a commit that holds `runner_tools.py`, and delete the ast extractors, the raises, `FAILURE_TAXONOMY_PATH` and the 4 tests of the raise
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_context.py tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py`

## 2. Documents

- [x] 2.1 State the source of the facts in the docstrings of `plan_item` and `_read_fact_file`, and in the live run paragraph of `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4663 confirms after the rollout that the Service log holds no `Staged source moved or missing` line for 24 h, and that dan-petty/dotfiles#1, dan-petty/homelab#1 and dan-petty/homelab#2 get a stage verdict.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
