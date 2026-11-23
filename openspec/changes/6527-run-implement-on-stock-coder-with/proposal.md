# Proposal

## Why

The implement job succeeds in 40% of graded attempts (7 days to 2026-11-20), under the 60% band, so #6519 asks for a re-architecture. Item #6527 keeps the pydantic-ai-harness `Coder` but replaces its shell with a 611-line allowlist, turns off the repository context, the skills and the compaction, and starts a new conversation for each task group. The change runs the stock agent instead, and it removes the code of the allowlist and of the refusal counts.

## What Changes

- `build_agent` builds the stock `Coder` with `repo_context` on, the `Skills` capability over the skill folder of the repository, `RequireVerification` with the project checks and `WrapUpAtLimits`, and the harness `Shell` with no allowed command and no denied command.
- The shell of a step is the harness shell with the tool `run_command`, the wait of `roadmap.implement.command_timeout_seconds` and the environment of `shell_environment`, built by `step_shell` of `src/devops_cli/roadmap/implement/implement_shell.py`.
- One `Conversation` with compaction carries every task group of an item: `run_step` fills a `StepConversation` and the group loop of `src/devops_cli/roadmap/implement/implement_run.py:1104:outcome = run_step(` keeps it for the item.
- The tool call log shows a first word only when the runner program table `RUNNER_TOOLS` holds it, and it holds no refused count and no stop at a refusal limit.
- The digest of progress counts the successful edits of the last `roadmap.implement.extension_calls` tool calls, and the three refusal settings go with their messages, their order checks and their entries of the cluster configuration.
- The verification grammar lives in `src/devops_cli/roadmap/verification_command.py`, and the stage, the plan reader, the step, the run, the tool log and the toolchain preset read it there.
- `tests/roadmap/test_roadmap_plan_rewrite.py` and `tests/roadmap/test_roadmap_step_files.py` read the verification grammar from the new module too, so the suite collects after the shell policy goes.
- `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/implement/implement_shell_refusal.py` and the tests that cover only the allowlist, the pipe reader and the refusal hint are deleted.
- The implement prompt names the stock shell and holds no programs table, no local commands table and no refusal table.
- Each version row of the grade report gives its all-attempt count and the share of the attempts that an infrastructure cut ended.
- The trace requirement of the log line names the runner program table and the `refused` outcome of a call that repeats a failed call.
- The change carries a spec delta: the shell of the implement agent, its settings, its stop reason, its log line and the grade report are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/shell`: The implement agent runs the stock shell with no allowlist, The shell tool admits only the project's programs, The shell admits a read pipe and the checkout prefix, The shell of the agent refuses a command that starts with a bang, The python -c refusal names the write_file call first, The implement prompt names the refusal of a heredoc, Consecutive refusals stop the step, A chain of allowed programs names two calls, The pipe refusal names read_file, The refusal table names openspec and devops
- `roadmap-implement-step/model-calls`: The agent of a step reads the project instructions and its skills, The agent of a step requires the project checks and wraps up at its limits, One conversation carries the task groups of an item
- `roadmap-implement-step/budgets`: Each limit that ends an implement step is a setting, An implement limit has a ceiling, The implement settings hold no refusal count, The digest of progress holds counts of the tool log, A step that makes progress gets one extension of its token budget, A step with no progress at its token budget stops as before, The reason of a stop at the token budget names its cause, The Job log and the outcome show the extension, The limits that end an implement step are settings, An implement limit has a ceiling and an order
- `roadmap-implement-step/trace`: The reason of a stopped run counts the retried tool calls, Every tool call of a step writes one line to the Job log, The reason of a stopped run counts the refused and the retried tool calls
- `roadmap-job-grades`: A version row counts every attempt and gives its infrastructure share

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_shell.py`, `src/devops_cli/roadmap/verification_command.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_rewrite.py`, `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/roadmap/stage/stage_move.py`, `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_eval_run.py`, `src/devops_cli/roadmap/implement/implement_eval_harbor_run.py`, `src/devops_cli/roadmap/implement/implement_limits.py`, `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/tools.py`, `src/devops_cli/roadmap/toolchains.py`, `src/devops_cli/roadmap/step_rules.py`, `src/devops_cli/roadmap/implement/implement_amend.py`, `src/devops_cli/roadmap/implement/implement_report.py`, `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/implement/implement_shell_refusal.py`, `src/devops_cli/roadmap/job_grade_report.py`, `k8s/devops/configmap.example.yaml`
- Documents: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/package-layout.md`, `docs/roadmap/implement.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/test_roadmap_plan_rewrite.py`, `tests/roadmap/test_roadmap_step_files.py`, `tests/roadmap/stage/test_roadmap_stage_task_verification.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/implement/test_roadmap_implement_extension.py`, `tests/roadmap/implement/test_roadmap_implement_tool_log.py`, `tests/config/test_roadmap_job_limit_settings.py`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`, `tests/ai/test_ai_task_loader.py`, `tests/roadmap/test_roadmap_step_rules.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/invariants/test_change_folders.py`, `tests/roadmap/implement/test_roadmap_implement_negative_search.py`, `tests/roadmap/implement/test_roadmap_implement_verification_class.py`, `tests/roadmap/implement/test_roadmap_implement_verification_reason.py`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, `tests/roadmap/implement/test_roadmap_implement_read_pipe.py`, `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`, `tests/roadmap/test_job_grade_report.py`, `tests/roadmap/__snapshots__/test_job_grade_report.ambr`, `tests/k8s/test_k8s_configmap.py`, `tests/ai/spend/test_hosted_group_prices.py`, `tests/roadmap/test_roadmap_fix_checks_row.py`

## Feasibility

- The premise of the issue is the allowlist that replaces the stock shell, and `probes` confirms the module: `The path `implement_shell_policy.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_shell_policy.py`. No commit in the history deleted or renamed it.`
- `probes` says `The path `AGENTS.md` is a file of the staging commit.`, so `repo_context` has the project instructions to read.
- The `file_symbols` call showed `src/devops_cli/roadmap/implement/implement_step.py:def build_agent` and `src/devops_cli/roadmap/implement/implement_step.py:def run_step`, so the builder and the run of a step are in that module.
- The `file_symbols` call showed `src/devops_cli/roadmap/implement/implement_run.py:def _groups`, and the read of the group loop showed `src/devops_cli/roadmap/implement/implement_run.py:1104:outcome = run_step(`, so each group of an item starts a step of its own and keeps no conversation.
- The `read_file` call showed `src/devops_cli/roadmap/implement/implement_tool_log.py:97:_KNOWN_PROGRAMS = frozenset(` over `IMPLEMENT_ALLOWED_PROGRAMS` and the replacements of the shell policy, so the log's program table comes from the allowlist today.
- The `read_file` call of `src/devops_cli/roadmap/tools.py` showed `src/devops_cli/roadmap/tools.py:206:return tuple(name for name, entry in TOOLS.items() if holder in entry.holders)`, so `src/devops_cli/roadmap/tools.py:def tool_names` gives the agent tool names of a holder and no program of the image.
- The `read_file` call of `src/devops_cli/roadmap/runner_tools.py` showed `src/devops_cli/roadmap/runner_tools.py:119:RUNNER_TOOLS: tuple[RunnerTool, ...] = (` and `src/devops_cli/roadmap/runner_tools.py:275:def tool_names() -> tuple[str, ...]:` whose body returns `tuple(tool.name for tool in RUNNER_TOOLS)`, so the program names of the runner image come from `src/devops_cli/roadmap/runner_tools.py:def tool_names`.
- The `search_code` call for `from devops_cli.roadmap.implement.implement_shell_policy import` returned 36 import lines, and each file is in the `changes` of a group or is deleted by group 14: `tests/roadmap/test_roadmap_step_files.py:10:from devops_cli.roadmap.implement.implement_shell_policy import verification_problem` and `tests/roadmap/test_roadmap_plan_rewrite.py:10:from devops_cli.roadmap.implement.implement_shell_policy import Verification, read_verification` are two of them, and group 2 rewrites both.
- The `references` call for `implement_shell_policy` returned 96 files and 189 lines; `tests/module_durations.json` and `tests/fixtures/roadmap_eval` keep the name as history, and a decision leaves them.
- The `read_file` call showed `src/devops_cli/roadmap/implement/implement_tool_log.py:497:self._note(call.tool_name, program, ToolOutcome.REFUSED, digest=digest)`, so the `refused` outcome stays for a call that repeats a failed call and only the shell refusal goes.
- The `read_file` call showed `src/devops_cli/roadmap/implement/implement_tool_log.py:541:in_a_row = self.limits.max_consecutive_refusals` and `src/devops_cli/roadmap/implement/implement_tool_log.py:546:if refused and sum(self.refused.values()) > self.limits.max_refusals:`, so group 8 removes both stops before group 9 removes the settings they read.
- The `read_file` call showed `src/devops_cli/roadmap/implement/implement_limits.py:192:self._max_refused = limits.extension_max_refused` and `src/devops_cli/roadmap/implement/implement_limits.py:def extends`, so group 6 removes the refused count of the digest and the read of its setting.
- The `read_file` call showed `src/devops_cli/roadmap/implement/implement_step.py:904:refused=log.refused_text(), retried=log.retried`, so group 7 removes the refused count of the stop reason before group 8 removes `refused_text()`.
- The staged constants that the budgets scenarios state are `src/devops_cli/config/defaults.py:1100:DEFAULT_ROADMAP_IMPLEMENT_MAX_REQUESTS: int = 500`, `src/devops_cli/config/defaults.py:1101:DEFAULT_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS: int = 1500`, `src/devops_cli/config/defaults.py:1108:DEFAULT_ROADMAP_IMPLEMENT_TOOL_RETRIES: int = 5` and `src/devops_cli/config/defaults.py:1124:DEFAULT_ROADMAP_IMPLEMENT_EXTENSION_CALLS: int = 20`.
- Precondition of `src/devops_cli/roadmap/implement/implement_step.py:def build_agent`: a checkout of the repository, which its `source` argument names. The test of group 1 passes a model script and a temporary folder, so it reaches no network and no cluster.
- Precondition of `src/devops_cli/roadmap/implement/implement_step.py:def run_step`: a checkout of the repository and a client of the roadmap store. The test of group 4 passes a stub store and a temporary folder, so it reaches no network and no cluster.
- Precondition of the group loop at `src/devops_cli/roadmap/implement/implement_run.py:1104:outcome = run_step(`: a checkout of the repository, a client of the roadmap store and a client of the AI gateway. That loop holds all three already, and the change adds no call.
- The harness names `Skills`, `RequireVerification`, `WrapUpAtLimits` and `repo_context` are `not checked`: the package is no file of this repository. The first check of group 1 runs `uv run python -c "from pydantic_ai_harness.coder import Coder"` and then `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py`.
- The plan adds no command, no option and no failure class: `uv run devops ci test`, `uv run devops ci docs`, `uv run devops ci --check --only k8s` and `uv run devops roadmap eval stage --replay` run programs of the runner image (`uv`, `python`, `devops`, `git`, `kubectl`), and the plan names no `NOT_IN_RUNNER` program. The pod keeps `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `runAsNonRoot: true`.
- The issue holds its acceptance list under the heading `## Acceptance` and no heading `Acceptance criteria`, so `criteria` is empty; the two items of that list are delivered by groups 1 and 15, and the 30 graded attempts of the second item stay with the follow-up #6768 of the refine block.
- Group 3 changes a check of the stage job, so it runs `uv run devops roadmap eval stage --replay` and states the score before and after the change; the score after the change must not be below the score before it.

## Existing Tool Considered

pydantic-ai-harness supplies the agent loop, the `Coder` file and shell tools, `LocalWorkspace`, the context controls and compaction, `Skills`, `RequireVerification` and `WrapUpAtLimits`; the change builds only `project_checks`, `step_shell` and the conversation hand-off. It deletes `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/implement/implement_shell_refusal.py`, the refused count of `src/devops_cli/roadmap/implement/implement_tool_log.py` and the three refusal settings of `src/devops_cli/config/settings.py`.

## Dependencies

None.
