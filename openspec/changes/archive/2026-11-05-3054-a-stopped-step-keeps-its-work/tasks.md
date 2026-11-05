# Tasks

## 1. Keep the ticked and verified tasks of a step

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`. Changes: `src/devops_cli/roadmap/implement_wip.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_wip.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_implement_wip.py`, add the tests of the step: a stopped step keeps the first task; its diff holds only the later work; a second step starts from the kept task and ends done in one commit; a task that fails its verification is not kept; a lint error after the last tick keeps the ticked work; a stray file stays out of the commit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_wip.py`
- [x] 1.2 Add `WipKeeper` in `src/devops_cli/roadmap/implement_wip.py`, the hook `after_call` of `ToolCallLog`, and the use of the keeper in `run_step`: the exit checks judge the folded work, a stop resets to the last `wip:` commit, and a done step folds the commits into its own
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_wip.py`

## 2. Push and record the work in progress in the job

Reads: `src/devops_cli/roadmap/implement_run.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/store.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_wip_job.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_implement_wip_job.py`, add a replay of a step that is killed after three of five tasks: `origin` holds three `wip:` commits before the step ends, the stop comment names the kept work, the record holds `implement.wip`, and a second Job after `implement: retry` does the two remaining tasks and leaves no `wip:` commit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_wip_job.py`
- [x] 2.2 In `src/devops_cli/roadmap/implement_run.py`, push and record each `wip:` commit, add the kept work to the stop comment, and remove the record when the group passes. Add the key `implement.wip` to `ImplementRecordKey`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_wip_job.py`

## 3. Tell the agent and the reader

Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/test_roadmap_implement_step.py`.

- [x] 3.1 In `src/devops_cli/ai/tasks/roadmap_implement_step.md`, say which work the job keeps and that a ticked task is done. In `docs/ROADMAP_WORKFLOW.md`, add `implement.wip` to the table of the job record. Update the test that quotes the prompt
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py`
  - Verification: `uv run devops docs check`
