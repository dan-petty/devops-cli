# Tasks

## 1. The rule and the step budget

- [x] 1.1 Add the table-driven tests on the pilot 3 shapes: the shapes that a person finished extend, the shapes that spin halt, a second limit halts, the ceiling holds, a missing digest falls back, the item budget holds, the counter, the ceiling setting, and the step through `run_step`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_extension.py`
- [x] 1.2 Add the constants, the setting `roadmap.implement.step_token_ceiling`, `progress_digest` and the window of `ToolCallLog`, the rule `extends`, the extension of `StepBudget`, the field `extension` of `StepOutcome`, the counter and the messages
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_extension.py tests/roadmap/implement/test_roadmap_implement_limits.py tests/roadmap/implement/test_roadmap_implement_tool_log.py`

## 2. The record and the comments of the job

- [x] 2.1 Add tests for the ready comment, the stop comment and the record of an extended step, and for a run with no extension
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_extension.py`
- [x] 2.2 Keep the extension in `implement.spend` and list it in the ready comment and the stop comment
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_extension.py tests/roadmap/implement/test_roadmap_implement_job.py`

## 3. Documents

- [x] 3.1 Describe the extension in `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md`, and regenerate the configuration, variable and metric documents
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
