# Tasks

## 1. Find the stray files of a group

Reads: `src/devops_cli/roadmap/step_files.py`, `tests/support/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_strays.py` (new), `tests/roadmap/test_roadmap_implement_strays.py` (new).

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_implement_strays.py` for the scenarios of "A step removes the stray files of the agent" that `stray_files` decides: a root file, a path of the `Changes:` line, a path in a task, the change folder, a new test file next to a named test file, a test file in another directory, and a path with `./`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_strays.py` fails on the base
- [x] 1.2 Add `stray_files` in `src/devops_cli/roadmap/implement_strays.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_strays.py` passes

## 2. Remove the stray files before the exit checks

Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_eval_properties.py`, `src/devops_cli/roadmap/implement_eval_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_strays.py`, `tests/roadmap/test_roadmap_implement_eval_properties.py`, `tests/roadmap/test_roadmap_implement_eval_run.py`, `tests/roadmap/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_implement_step_repair.py`, `tests/roadmap/test_roadmap_implement_step_format.py`, `tests/roadmap/test_roadmap_implement_step_output_cap.py`, `tests/roadmap/test_roadmap_implement_job.py`.

- [x] 2.1 Write failing replay tests with a stub model in `tests/roadmap/test_roadmap_implement_strays.py`: the agent writes `tmp_test_x.py` with an unused import in the root, and the step ends done with the file gone from the tree and from the commit; a new test file next to `tests/test_sample.py` stays and is in the commit; a failed static check gives an extra turn whose message names the removed file; a stray file written in the extra turn is removed and does not stop the step; the outcome lists the removed files; and eval tests that a removed file still fails `diff_scope` and `no_scratch`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_strays.py` fails on the base
- [x] 2.2 Remove the stray files at the start of `_exit_failure` and after the extra turn, record them in `ToolCallLog` and `StepOutcome.removed`, name them in the message of the extra turn, and pass them to `diff_scope` and `no_scratch` of the eval; make the step tests write files that the group allows
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_strays.py tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_step_repair.py tests/roadmap/test_roadmap_implement_step_ticks.py tests/roadmap/test_roadmap_implement_tool_log.py tests/roadmap/test_roadmap_implement_eval_properties.py tests/roadmap/test_roadmap_implement_eval_run.py tests/roadmap/test_roadmap_implement_job.py`

## 3. The prompt, the table and the documents

Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_prompt.py`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_prompt.py`, `README.md`.

- [ ] 3.1 Write a failing test in `tests/roadmap/test_roadmap_implement_prompt.py` that the prompt says that the step deletes a file that the group does not name, and that it keeps the rule of #3007
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py` fails on the base
- [ ] 3.2 Add the sentence to the prompt, show the removed files in the table of the command, and add the rule to the help text
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py tests/roadmap/test_roadmap_implement_command.py`
- [ ] 3.3 Regenerate the command documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 4. Fail-to-pass and archive

- [ ] 4.1 Run the fail-to-pass check on the new tests
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] 4.2 Archive the change
  - Verification: `uv run devops openspec archive 3092-step-removes-stray-files` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
