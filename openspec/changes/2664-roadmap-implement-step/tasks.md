# Tasks

## 1. The harness dependency and the implement task

- [x] Add failing tests: the defaults of `ai.tasks.implement`, a window set in the config file, and the section list of the unknown-key test
  - Verification: `uv run devops ci test tests/test_ai_task_implement.py tests/config/test_unknown_config_keys.py`
- [x] Pin `pydantic-ai-harness[coder]==0.59.0` with `pydantic-ai==2.59.0` and `genai-prices==0.1.13` in `pyproject.toml`, and refresh `uv.lock`
  - Verification: `uv lock --check` and `uv audit`
- [x] Add the `implement` task to `AITasksConfig` and to the task list of `devops ai`, and the limits of the step to `config/constants.py`
  - Verification: `uv run devops ci test tests/test_ai_task_implement.py tests/config/test_unknown_config_keys.py`
- [x] Move the stream drain and the spend record of refine's investigation to `roadmap/agent_run.py`
  - Verification: `uv run devops ci test tests/test_roadmap_refine_investigation.py tests/test_roadmap_agent_run.py`

## 2. The groups, the inputs and the measure of a step

- [x] Add failing tests: the groups of a `tasks.md`, the verification commands and the files of a group, the first request of a step, a refused window, a dirty checkout and a missing change
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`
- [x] Add `parse_task_groups`, `build_step_inputs` and the refusals in `roadmap/implement_step.py`, the prompt `roadmap_implement_step.md` and `RoadmapImplementError`
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`

## 3. The run, the exit checks and the commit

- [x] Add failing tests: a done step with one commit, a failed verification, a failed static check, an unticked task, a changed group, the shell allowlist, the limits, the tools of the agent and the spend record
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`
- [x] Add the tuned `Coder` agent, the run with its limits, the exit checks, the commit and the reset, and `StepOutcome`
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py tests/test_roadmap_agent_run.py`

## 4. The command and the documentation

- [x] Add failing CLI tests: the table, the JSON, the exit code of a stopped step, the refusal output and the dry run
  - Verification: `uv run devops ci test tests/test_roadmap_implement_command.py`
- [x] Add `devops roadmap implement`, its help and messages, and the dry-run plan
  - Verification: `uv run devops ci test tests/test_roadmap_implement_command.py tests/test_roadmap_dry_runs.py`
- [x] Add the knowledge base note for the harness
  - Verification: `uv run devops ci test tests/test_kb_manuals_metadata.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 5. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2664-roadmap-implement-step`

## Workflow follow-up

- The `max_input_tokens` window on the `devops-coder` gateway route is not part of this change. The design records why. The step measures its inputs itself.
- The job that runs the step for each group, and the retry policy, are #2665. The runner is the third sub-issue of #2661.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
