# Tasks

## 1. Choose the refusal hint from the whole refused command

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_shell_refusal.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_tool_log.py`, `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`. Changes: `src/devops_cli/roadmap/implement/implement_shell_refusal.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`.

- [ ] 1.1 Write tests in `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py` first: `test_the_refusal_of_python_code_names_the_write_file_call_first` calls `refusal_hint` with `uv run python -c 'a=1; print(a)'`, with a new line and with a heredoc, and asserts that each text starts with the `write_file` instruction and names `.data/agent/scratch/` and `uv run python`; it also drives `run_command` and asserts that the refusal carries that text. Add `test_the_hint_for_python_code_holds_no_word_of_the_refused_command` asserting that the hint holds no word of the command
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_refusal.py` fails on the base
- [ ] 1.2 Give `refusal_hint` in `src/devops_cli/roadmap/implement/implement_shell_refusal.py` the whole refused command, and read the first word from it. Add a helper that spots Python code with `-c` or a heredoc and match it first, then the replacement table, then the chain text for a program of the shell. Pass the stripped command from `_RefusingToolset.call_tool`. Add `implement_refusal_python_code` to `src/devops_cli/lang/en/messages.py` and rewrite `implement_refusal_operator` to the two-call text with `git status --short` and `git log --oneline -5`. Update `test_the_refusal_of_an_operator_states_the_rule_of_one_command_in_each_call` and `test_the_refusal_of_python_code_names_the_operator_in_the_code_and_a_script_file` in `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_refusal.py` passes

## 2. Name read_file in the pipe refusal

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_read_pipe.py`. Changes: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_read_pipe.py`.

- [ ] 2.1 Write the test `test_a_pipe_to_a_program_that_the_shell_does_not_allow_names_read_file` in `tests/roadmap/implement/test_roadmap_implement_read_pipe.py` first: it calls `pipe_refusal` with `git status | sed -n 1,20p` and asserts that the text names `read_file` with `offset` and `limit` and still names `sed`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_read_pipe.py` fails on the base
- [ ] 2.2 Change `implement_refusal_pipe` in `src/devops_cli/lang/en/messages.py` to name `read_file` with `offset` and `limit`, and keep the part of `_pipe_text` in `src/devops_cli/roadmap/implement/implement_shell_policy.py` that names the program after the pipe. Update the pipe tests in `tests/roadmap/implement/test_roadmap_implement_read_pipe.py` that assert the old text
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_read_pipe.py` passes

## 3. Name the project command for openspec and devops refusals

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 3.1 Write the test `test_the_refusal_of_a_project_command_names_the_uv_run_form` in `tests/roadmap/implement/test_roadmap_implement_shell_policy.py` first: it asserts that `SHELL_REFUSALS` holds an `openspec` row with `uv run devops openspec check` and a `devops` row with `uv run devops`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py` fails on the base
- [ ] 3.2 Add the two rows to `SHELL_REFUSALS` in `src/devops_cli/roadmap/implement/implement_shell_policy.py`. Edit `test_a_refused_program_is_not_an_allowed_program` in `tests/roadmap/implement/test_roadmap_implement_shell_policy.py` so its first assertion compares the refusals with `IMPLEMENT_SHELL_PROGRAMS`, because `openspec` and `devops` are verification first words and no shell program; keep the test and its name, and say why in its docstring
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py` passes
- [ ] 3.3 Edit `docs/ROADMAP_WORKFLOW.md` so its refusal table holds the two new rows of `SHELL_REFUSALS`
  - Verification: `$ uv run devops ci docs` passes

## 4. Offer create_directory and make the scratch directory

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_command.py`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`, `AGENTS.md`. Changes: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`.

- [ ] 4.1 Write the tests in `tests/roadmap/implement/test_roadmap_implement_step.py` and `tests/roadmap/implement/test_roadmap_implement_job.py` first: `test_the_agent_has_the_file_tools_and_the_shell_and_no_delegate` in `tests/roadmap/implement/test_roadmap_implement_step.py` is updated to assert `create_directory` is in `script.tools_offered[0]`; `test_the_step_offers_create_directory` asserts that `create_directory` is in `IMPLEMENT_LOCAL_TOOL_NAMES` and among the tools of the built agent, that a call makes the directory inside the checkout, and that a call with a path that climbs out of the checkout makes nothing; `test_the_job_makes_the_scratch_directory` in `tests/roadmap/implement/test_roadmap_implement_job.py` asserts that the job makes `.data/agent/scratch/` in the checkout before the first step and that `git check-ignore` reports it ignored. The suites `tests/roadmap/implement/test_roadmap_implement_job.py` and `tests/roadmap/implement/test_roadmap_implement_command.py` must pass with the new tool in the tool list
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py` fails on the base
- [ ] 4.2 Add `create_directory` to the `FileSystem` capability tools in `_tune` in `src/devops_cli/roadmap/implement/implement_step.py`, add its name to `IMPLEMENT_LOCAL_TOOL_NAMES`, and make the scratch path `.data/agent/scratch/` in the checkout in `_worktree` in `src/devops_cli/roadmap/implement/implement_run.py`. Update `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` lines 34 and 59 to describe the harness `create_directory` tool. Keep `test_the_job_runs_no_step_unless_it_is_in_a_runner` in `tests/roadmap/implement/test_roadmap_implement_job.py` and `test_a_done_step_prints_its_outcome_as_json_and_exits_0` in `tests/roadmap/implement/test_roadmap_implement_command.py` passing
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py` passes

## 5. Replace the python -c mkdir text of the prompt

Kind: other. Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`.

- [ ] 5.1 Replace the mkdir sentence at line 40 and the one at line 59 of `src/devops_cli/ai/tasks/roadmap_implement_step.md` with `create_directory`: the job makes `.data/agent/scratch/` before the first step, and any other directory comes from the tool. Add a test to `tests/roadmap/implement/test_roadmap_implement_prompt.py` that asserts that the rendered prompt names `create_directory` and holds no `python -c` command that calls `mkdir`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py` passes

## 6. Name the directory tool in the workflow document and replay the new tests

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, `tests/invariants/test_roadmap_workflow_doc.py`, `src/devops_cli/ci/fail_to_pass.py`, `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`. Changes: `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`.

- [ ] 6.1 Add the test `test_the_shell_section_of_the_document_names_the_directory_tool_and_the_scratch_directory` to `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, next to `test_the_document_of_the_workflow_holds_the_same_tables`: it reads `docs/ROADMAP_WORKFLOW.md`, takes the text after `## The shell of a step` up to the next heading, and asserts that it names `create_directory` and `.data/agent/scratch/`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py` fails on the base
- [ ] 6.2 Edit `docs/ROADMAP_WORKFLOW.md` so the section `## The shell of a step` names `create_directory` and the `.data/agent/scratch/` directory that the job makes before the first step. Then run `uv run devops ci fail-to-pass --base origin/main` and read its report: each new test of the earlier groups fails on the base commit, and the command exits 0
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py` passes

## Criteria

- Group 1: A test (written first, fails on the base) gives `refusal_hint` a refused `uv run python -c "a=1; print(a)"` and proves that the text starts with the `write_file` instruction.
- Group 1: A test gives a refused `git status && git log` and proves that the text names two separate calls.
- Group 4: A test proves that the step offers `create_directory` and that the job makes `.data/agent/scratch/` before step 1.
- Group 5: A test proves that the prompt holds no `python -c` mkdir text.
- Group 6: `uv run devops ci fail-to-pass --base origin/main` shows that the new tests fail on the base.
- Pending person: Measure in telemetry, 7 days after the release (runner log lines in Loki): refusals per implement run go down from about 4, a repeat of the same refused form after its hint goes to 0, stops after 3 refusals in a row go to 0, and `python -c` mkdir calls go to 0., It reads the Loki logs 7 days after the release, and no offline test and no task group can measure it.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
