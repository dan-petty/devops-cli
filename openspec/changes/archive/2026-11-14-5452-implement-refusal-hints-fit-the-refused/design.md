# Design

## Decisions

- **Pass the whole refused command to `refusal_hint` and match the Python-code rule first.**: The first word gives `uv run python -c` and `git status && git log` the same text. The whole form tells them apart, and the file instruction comes first for Python code.
- **Keep the pipe text in `pipe_refusal`, which already splits the stages.**: It is the one function that reads the program after the pipe, so one text names both `sed` and `read_file` with `offset` and `limit`.
- **Tune the harness `FileSystem` capability to offer `create_directory`.**: The locked harness 0.59.0 provides `create_directory` with safe workspace path resolution. `Coder` registers only `FILE_TOOL_NAMES`. Adding `create_directory` in `_tune` gives the harness tool without a new module.
- **Make `.data/agent/scratch/` in `_worktree`, before the first step.**: The job makes the checkout of the item there, so every run holds the directory before the first model request, and `.gitignore` keeps it out of the commit.
- **Update `test_the_agent_has_the_file_tools_and_the_shell_and_no_delegate` and run it in the group 4 verify.**: It pins the exact offered tool list. Group 4 updates it to include `create_directory` and names the module in its changes.
- **Keep the name `test_a_refused_program_is_not_an_allowed_program` and change its assertion to the shell programs.**: The step keeps every test that exists. Only the assertion changes to compare against `IMPLEMENT_SHELL_PROGRAMS`, with the reason in the test.
- **Update the pydantic-ai-harness knowledge base document.**: Lines 34 and 59 of `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` are updated to state that `FileSystem` has `create_directory` and the step adds it.
- **Carry spec deltas for `shell`, `inputs` and `budgets`.**: Adding `create_directory` updates the offered tools in both `shell` and `budgets` specs.
- **Give the last group the workflow document text and the test that reads it, and run the replay inside that group.**: A group that changes a document needs a verify that runs a test reading it. The replay proves the new tests fail on the base.
- **Leave the post-release measurement to a person.**: No offline test and no task group can read Loki 7 days after a release, so the criterion is `pending-person`.

## Rejected alternatives

- **Keep the hint selected from the first word of the command.**: `src/devops_cli/roadmap/implement/implement_shell_refusal.py:59:if word in IMPLEMENT_SHELL_PROGRAMS:` sends every allowed program to one text, and the run evidence of 71 refusals shows that the model repeats the form.
- **Make the scratch directory with `uv run python -c` from the prompt.**: `src/devops_cli/ai/tasks/roadmap_implement_step.md:40:Make the directory with ` is the text that the 14 mkdir calls follow, and the shell refuses the `;` and the new line of that form.
- **Build a custom `create_directory` tool or module.**: The locked harness 0.59.0 already provides `create_directory` in its `FileSystem` capability. Building a custom module violates AGENTS.md rule 3.
- **Let `write_file` make the parent directory of a new file.**: `write_file` in the harness does not create directories.
- **Edit the document in a group whose verify is the fail-to-pass replay.**: `run_fail_to_pass` replays changed test files on the base tree only. `test_the_document_of_the_workflow_holds_the_same_tables` reads the document, so the document group runs that test as its verify.
- **Leave the fail-to-pass replay to a person after the groups run.**: `run_fail_to_pass` runs in the checkout and needs no client, so a task group runs it as part of its work.
