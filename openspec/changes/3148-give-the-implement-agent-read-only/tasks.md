# Tasks

## 1. Name every tool of the step from the registry

Kind: behavior. Reads: `src/devops_cli/roadmap/tools.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `tests/roadmap/test_roadmap_tools.py`, `tests/roadmap/implement/test_roadmap_implement_command.py`. Changes: `src/devops_cli/roadmap/tools.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `tests/roadmap/test_roadmap_tools.py`.

- [ ] 1.1 Add `test_the_implement_holder_names_every_tool_of_the_step` to `tests/roadmap/test_roadmap_tools.py`: it asserts that `tool_names(HOLDER_IMPLEMENT)` gives `read_file`, `list_files`, `write_file`, `edit_file`, `grep` and `run_command`, that `read_file` stays in `tool_names(HOLDER_STAGE)`, and that `IMPLEMENT_LOCAL_TOOL_NAMES` equals that set. It fails because `read_file` and `list_files` name the stage holders only
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_tools.py tests/roadmap/implement/test_roadmap_implement_command.py` fails on the base
- [ ] 1.2 Give `read_file` and `list_files` the union of `_STAGE` and `_IMPLEMENT` in `TOOLS` of `src/devops_cli/roadmap/tools.py`, and keep their purpose text. In `src/devops_cli/roadmap/implement/implement_step.py`, set `IMPLEMENT_LOCAL_TOOL_NAMES` to `frozenset(tool_names(HOLDER_IMPLEMENT))`, and import `HOLDER_IMPLEMENT` and `tool_names` from `devops_cli.roadmap.tools`. The set stays the six names. The test `tests/roadmap/implement/test_roadmap_implement_command.py` imports `StepOutcome`, `StepStatus` and `render_outcome` from the module and keeps them unchanged
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_tools.py tests/roadmap/implement/test_roadmap_implement_command.py` passes

## 2. Count each tool call in the tool log

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `tests/roadmap/implement/test_roadmap_implement_tool_log.py`. Changes: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `tests/roadmap/implement/test_roadmap_implement_tool_log.py`.

- [ ] 2.1 Add `test_the_counts_of_each_tool` to `tests/roadmap/implement/test_roadmap_implement_tool_log.py`: two `read_file` calls and one `pr_describe` call give the counts two and one. It fails because `ToolCallLog` holds no count of each tool
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tool_log.py` fails on the base
- [ ] 2.2 Add `calls` to `ToolCallLog` of `src/devops_cli/roadmap/implement/implement_tool_log.py`: a `Counter[str]` that `_note` increments for each call, and a `calls_text()` that renders the counts from the most called to the least, cut to the same number of names as `refused_text()`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tool_log.py` passes

## 3. Put the tools table in the prompt

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `src/devops_cli/roadmap/tools.py`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`. Changes: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`.

- [ ] 3.1 Add `test_the_tools_table_lists_the_registry_tools` to `tests/roadmap/implement/test_roadmap_implement_prompt.py`: it calls `fill_prompt` and asserts that the prompt holds each name of `tool_names(HOLDER_IMPLEMENT)` with its read flag and its purpose, and no other tool name. It fails because the prompt names its tools in one sentence and holds no table
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py tests/roadmap/implement/test_roadmap_implement_shell_policy.py` fails on the base
- [ ] 3.2 Add `tools_table()` and `TOOLS_PLACEHOLDER = "{{tools}}"` to `src/devops_cli/roadmap/implement/implement_shell_policy.py`, render `| Tool | Access | Use |` from `tool_names(HOLDER_IMPLEMENT)` with the read flag as `read` or `write`, and replace the placeholder in `fill_prompt`. Put `{{tools}}` under a heading of `src/devops_cli/ai/tasks/roadmap_implement_step.md` and replace the sentence that lists the tools with a pointer to the table. Name the new placeholder in the test of the placeholders in `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py tests/roadmap/implement/test_roadmap_implement_shell_policy.py` passes
- [ ] 3.3 Edit `src/devops_cli/ai/tasks/roadmap_implement_step.md` to hold the `{{tools}}` placeholder and to point at the table
  - Verification: `$ uv run devops ci docs` passes

## 4. Name the tools of the Job in the pull request comment

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_trace.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`. Changes: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`.

- [ ] 4.1 Add `test_the_pull_request_comment_names_the_tools_of_the_job` to `tests/roadmap/implement/test_roadmap_implement_job.py`: it runs the Job with two groups and one failed check whose command names a path, and asserts that the comment holds the count of each tool that the steps called, such as `read_file` and `pr_describe`, that the line of the counts holds no argument of a tool call and no path of the checkout, and that the table of the steps keeps the failing command with its path. It fails because the comment holds no tool count
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py` fails on the base
- [ ] 4.2 Add `tool_counts: dict[str, int] = {}` to `StepOutcome` of `src/devops_cli/roadmap/implement/implement_step.py` and fill it from `log.calls` where the step builds the outcome. In `_comment` of `src/devops_cli/roadmap/implement/implement_run.py`, add one line under the table of the steps that sums the counts of `self.outcomes` by tool name, with a new template beside `implement_pull_comment` in `src/devops_cli/lang/en/messages.py`. Leave the table of the steps and its last failing command as they are
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py` passes

## 5. Score the step with and without its remote tools

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval_implement.py`, `src/devops_cli/roadmap/implement/implement_eval_run.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_eval_run.py`. Changes: `src/devops_cli/commands/roadmap_eval_implement.py`, `src/devops_cli/roadmap/implement/implement_eval_run.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_eval_run.py`.

- [ ] 5.1 Add `test_the_report_holds_the_tool_mode` to `tests/roadmap/implement/test_roadmap_implement_eval_run.py`: a dry run of `devops roadmap eval implement --dry-run` on one fixture, then a dry run with `--no-tools`, names the same fixture and base commit and states a different tool mode. It fails because the command has no `--no-tools` option and `RunReport` has no tool mode
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_run.py` fails on the base
- [ ] 5.2 Add the `--no-tools` option to `implement_cmd` in `src/devops_cli/commands/roadmap_eval_implement.py`, with its help text in `src/devops_cli/lang/en/help.py`. Thread `tools: bool = True` through `render_dry_run`, `run_case` and the step, so that a false value skips the build at `src/devops_cli/roadmap/implement/implement_step.py:1973:if mcp_toolset is None and settings.roadmap.implement.mcp:`. Add `tools: bool = True` to `RunReport` of `src/devops_cli/roadmap/implement/implement_eval_run.py` and state the mode in the report and in the dry-run text, with the words in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_run.py` passes

## 6. Drop the two lookups from the implementation role

Kind: behavior. Reads: `src/devops_cli/ai/mcp/roles.py`, `src/devops_cli/ai/mcp/server.py`, `src/devops_cli/roadmap/tools.py`, `tests/ai/mcp/test_mcp_roles.py`, `tests/ai/mcp/test_mcp_http.py`, `tests/roadmap/test_roadmap_tools.py`. Changes: `src/devops_cli/ai/mcp/roles.py`, `src/devops_cli/roadmap/tools.py`, `tests/ai/mcp/test_mcp_roles.py`, `tests/ai/mcp/test_mcp_http.py`, `tests/roadmap/test_roadmap_tools.py`.

- [ ] 6.1 Add `test_the_implementation_role_holds_no_security_lookup` to `tests/ai/mcp/test_mcp_roles.py`: it calls `tools_for_role(ROLE_IMPLEMENTATION, _catalogue())` and asserts that the held names hold neither `security_intel_network` nor `security_intel_package` and that the role holds 15 tools, and it changes `test_two_connections_with_different_roles_see_different_tool_lists` to `(28, 15, 16)` with the relation `(False, True, {"pr_describe"})`. It fails because the implementation role holds both lookups today
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_roles.py tests/ai/mcp/test_mcp_http.py tests/roadmap/test_roadmap_tools.py` fails on the base
- [ ] 6.2 In `src/devops_cli/ai/mcp/roles.py`, the implementation row of `_JOB_ROLE_TOOLS` becomes `_GITHUB_READS | {"pr_describe"}`. In `src/devops_cli/roadmap/tools.py`, give `security_intel_network` and `security_intel_package` a new holder set `_PLANNING_AND_REVIEW` of `HOLDER_PLANNING` and `HOLDER_REVIEW` in place of `_EVERY_JOB_ROLE`. Change the count assertions of `tests/ai/mcp/test_mcp_http.py` and `tests/ai/mcp/test_mcp_roles.py` to `(28, 15, 16)`, and assert in `tests/roadmap/test_roadmap_tools.py` that `tool_names(HOLDER_IMPLEMENTATION)` holds neither lookup. The planning and review roles keep both
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_roles.py tests/ai/mcp/test_mcp_http.py tests/roadmap/test_roadmap_tools.py` passes

## 7. State the read forms of the code intelligence in the command table

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, `tests/invariants/test_roadmap_workflow_doc.py`. Changes: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`.

- [ ] 7.1 Add `test_the_code_intelligence_commands_are_reads` to `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`: it reads `LOCAL_COMMANDS` and asserts that the `ai ast` and `ai repomap` entries have access read, that neither use text names `--output`, and that the table holds no command with the access `network`. It fails because the `ai ast` entry has access write
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py tests/invariants/test_roadmap_workflow_doc.py` fails on the base
- [ ] 7.2 In `LOCAL_COMMANDS` of `src/devops_cli/roadmap/implement/implement_shell_policy.py`, give the `("ai", "ast")` entry `ShellAccess.READ` and a use text that names `parse` and `graph` and no `--output`, and keep `("ai", "repomap")` read. Change the command table of `docs/ROADMAP_WORKFLOW.md` to the same text
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py tests/invariants/test_roadmap_workflow_doc.py` passes
- [ ] 7.3 Edit `docs/ROADMAP_WORKFLOW.md` to hold the read form of the `ai ast` row
  - Verification: `$ uv run devops ci docs` passes

## 8. Regenerate the command reference and state the eval modes

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`.

- [ ] 8.1 Run `uv run devops docs generate` to write `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` with the `--no-tools` option of `devops roadmap eval implement`. Edit `docs/ROADMAP_WORKFLOW.md` to state the tools table of the step, the tool counts of the pull request comment, the 15 tools of the implementation role, and the two runs of the eval on one fixture set
  - Verification: `$ uv run devops ci docs` passes
- [ ] 8.2 Edit `docs/ROADMAP_WORKFLOW.md` and `docs/CLI_REFERENCE.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 4: The implement step lists the tools it offers, and the PR comment of a Job shows which tool calls it made.
- Group 5: `devops roadmap eval implement` states its score with and without the tools on the same fixtures.
- Group 6: A tool that the agent has cannot write a file or reach the network.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
