# Design

## Decisions

- **Pass the whole refused command to `refusal_hint` and match the Python-code rule first.**: The first word gives `uv run python -c` and `git status && git log` the same text; the whole form tells them apart, and the file instruction comes first for Python code.
- **Keep the pipe text in `pipe_refusal`, which already splits the stages.**: It is the one function that reads the program after the pipe, so one text names both `sed` and `read_file` with `offset` and `limit`.
- **Build a small project `create_directory` tool instead of a harness tool.**: The locked harness 0.59.0 gives six tools and its `write_file` creates no directory, so no installed tool covers the need.
- **Make `.data/agent/scratch/` in `_worktree`, before the first step.**: The job makes the checkout of the item there, so every run holds the directory before the first model request, and `.gitignore:73:.data/*` keeps it out of the commit.
- **Read `tests/roadmap/implement/test_roadmap_implement_job.py` and `tests/roadmap/implement/test_roadmap_implement_command.py` in the group that changes their modules.**: They are the suites of `implement_run` and `implement_step`, so the step that changes those modules must see them to keep them passing, and the new tests of the scratch directory sit in one module so the group has one verify command.
- **Keep the name `test_a_refused_program_is_not_an_allowed_program` and change its assertion to the shell programs.**: The step keeps every test that exists, and a renamed test counts as a lost test; only the assertion changes, with the reason in the test.
- **Give the last group the workflow document text and the test that reads it, and run the replay inside that group.**: A group that changes a document needs a verify that runs a test reading it, so that group's verify runs `test_the_document_of_the_workflow_holds_the_same_tables` and the new assertion on the exact text; the replay proves the new tests fail on the base and says nothing about the head document, so it is a command of the step's work and of the pull request check.
- **Leave the post-release measurement to a person.**: No offline test and no task group can read Loki 7 days after a release, so the criterion is `pending-person`.

## Rejected alternatives

- **Keep the hint selected from the first word of the command.**: `src/devops_cli/roadmap/implement/implement_shell_refusal.py:59:if word in IMPLEMENT_SHELL_PROGRAMS:` sends every allowed program to one text, and the run evidence of 71 refusals shows that the model repeats the form.
- **Make the scratch directory with `uv run python -c` from the prompt.**: `src/devops_cli/ai/tasks/roadmap_implement_step.md:40:Make the directory with ` is the text that the 14 mkdir calls follow, and the shell refuses the `;` and the new line of that form.
- **Adopt a `create_directory` tool of pydantic-ai-harness.**: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md:34:gives an agent six tools`, and no one of them is a directory tool.
- **Let `write_file` make the parent directory of a new file.**: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md:59:does not create a directory. A shell command creates it.`, so the model made the directory with a refused shell command.
- **Edit the document in a group whose verify is the fail-to-pass replay.**: `src/devops_cli/ci/fail_to_pass.py:706:def run_fail_to_pass(root: Path, *, base: str, head: str = "HEAD") -> FailToPassReport:` replays the changed test files on the base tree only, and `tests/roadmap/implement/test_roadmap_implement_shell_policy.py:476:text = (REPO_ROOT / "docs" / "ROADMAP_WORKFLOW.md").read_text(encoding="utf-8")` is the check that reads the document, so the document group runs that test as its verify.
- **Leave the fail-to-pass replay to a person after the groups run.**: `src/devops_cli/ci/fail_to_pass.py:706:def run_fail_to_pass(root: Path, *, base: str, head: str = "HEAD") -> FailToPassReport:` runs in the checkout and needs no client, so a task group runs it as part of its work.
