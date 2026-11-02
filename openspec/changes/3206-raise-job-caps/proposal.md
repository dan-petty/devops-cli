# Proposal

## Why

Issue #3206: the roadmap jobs carry limits that cut work short. A cut plan, a cut step or a stopped run costs a retry or a plan with less evidence. The limits were set when the jobs were new and the models had small windows. The owner decided (2026-11-02) to raise or remove the soft caps and the request timeouts. The owner keeps every limit that an outside system sets, the Kubernetes Job deadline, the admission policy, the RBAC and the memory limit. The owner also said that the cost of the model is no reason to keep a cap: the spend of the DeepSeek route is small.

## What Changes

- Every numeric limit of the roadmap jobs gets a class: `raised`, `guard`, `window`, `setting`, `kept` or `other`. A table in `tests/roadmap/test_roadmap_limit_classes.py` lists them with a reason, and the test fails when a limit is added with no class or when the table names a limit that is gone. The design holds the full table.
- The three time limits become settings with higher defaults: `roadmap.implement.request_timeout_seconds` (600 to 1200), `roadmap.implement.command_timeout_seconds` (900 to 1800) and `roadmap.implement.monitor_timeout_seconds` (1800 to 3600). Each has a variable. The three `CONST_ROADMAP_IMPLEMENT_*_TIMEOUT_SECONDS` constants go.
- The output cap of a reply of an implement step is a quarter of the context window of the task (32000 tokens of 128000). It was 16384 tokens. `CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS` goes.
- The stage run has no count of output tokens. They are in the messages, and the context window ends the tools of a run before the messages pass it. `CONST_ROADMAP_STAGE_MAX_OUTPUT_TOKENS` goes, and `UsageLimits` sets no `output_tokens_limit`.
- The counts of requests and tool calls stay as the loop guard of each job, 6 to 8 times higher: stage 200 calls and 250 requests (was 30 and 40), refine investigation 150 calls and 100 requests (was 20 and 12), implement 1500 calls and 500 requests (was 240 and 80). Without them, the Job deadline would be the only stop of a model that loops.
- The investigation of refine and of the alternatives check passes the context window of the `analysis` task to `investigate`, as the stage run does. The window ends the tools before the counts do, so the higher counts cannot make a request longer than the window. `analysis_window` moves from `stage.py` to `refine_investigation.py`.
- Caps that cut evidence rise: the step budget `roadmap.stage.step_tokens` default (40000 to 64000, half of the implement window), the packed file of a step (3000 to 8000 tokens), the tool result of a step (16000 to 40000 characters), the log of a failed check (6000 to 20000 characters), the answer of a refine tool (4000 to 8000 characters and 120 to 240 lines), the answers of the stage tools (commits 20 to 40, mapped files 20 to 40, spec text 8000 to 16000 characters), the alternatives check (searches 3 to 10, fact reads 6 to 30, body 4096 to 16384 tokens), and the refine context (searches 3 to 10, specs 5 to 10, requirement names 40 to 100, replies 5 to 10, reply size 1024 to 4096 tokens).
- Observable behavior changes (defaults, settings, variables and stop reasons), so the change carries spec deltas.
- The change fits one pull request.

The change keeps these limits, with the reason in the table: every size that GitHub sets (the body and the comment of 65536 characters), the rule of the project for a pull request body (1000 characters), the shape of a stop report that a person reads, the sizes that bound the secret masking and the memory, the verification pass (its slot sets no window), the comment cap against a loop of replies, the retries of a broken reply and of a refused tool call, the number of resends, the number of items of a round, the schedules, and the Job deadline, the admission policy, the Role and the memory limit, which #3063 owns. It does not touch `k8s/devops/`.

## Capabilities

### New Capabilities

- `roadmap-job-limits`: every numeric limit of the roadmap jobs has a class and a reason, and a raised limit fits the windows of the stack.

### Modified Capabilities

- `roadmap-stage`: the budget of a plan run, the tool answers, and the default of the step budget.
- `roadmap-implement-step`: the output cap is a share of the window, and the three time limits are settings.
- `roadmap-refine`: the investigation reads the context window of the `analysis` task.
- `roadmap-alternatives`: the check reads the context window, and the budget of the request.
- `roadmap-implement-job`: the defaults of the stall and the extension of the deadline.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/implement_step.py`, `implement_run.py`, `implement_hooks.py`, `implement_scoped_ci.py`, `implement_pull.py`, `stage_toolbox.py`, `stage.py`, `refine.py`, `refine_investigation.py`, `alternatives.py`.
- Documents: `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` (generated).
- Tests: `tests/roadmap/test_roadmap_limit_classes.py` (new), `tests/roadmap/test_roadmap_implement_timeouts.py` (new), and the tests that held the old numbers.
- Specs: the capabilities above, by archive. `roadmap-implement-job` changes the two defaults of the deadline settings.
- The stall and the extension of the progress-based Job deadline (#3063) follow the new watch: the stall is above the longest silent wait by 600 s (a test of that change holds the rule), so the defaults go from 2400 s and 3600 s to 4200 s and 5400 s. The change touches only those two defaults, their test and their spec text, not the deadline code.
- Follow-up outside this change: `k8s/devops/configmap.example.yaml` sets `step_tokens: 40000`, so the Service keeps 40000 until a person removes the line.

## Feasibility

- `UsageLimits` accepts `None` for each field: its fields default to `None`, and `_within_budget` of `refine_investigation.py` reads `limits.tool_calls_limit or 0`, which turns `None` into "no tool". So the request and tool call counts stay set. `output_tokens_limit` has no reader, so `stage_toolbox.py` drops it. The check: `uv run python -c "from pydantic_ai.usage import UsageLimits; print(UsageLimits())"` prints all fields as `None`.
- The messages of a run hold its output tokens, and `_within_window_of` removes the tools when the tokens of the messages and a quarter of the window reach the window. So a count of output tokens guards nothing that the window does not. `_tokens_of` counts the instructions again in every request (the JSON form of the messages), so the guard errs early; the test `test_the_window_of_the_analysis_task_ends_the_tools_before_the_counts_do` shows a window of 6000 tokens ends the tools within 10 requests.
- The default window of the `analysis` task is 32768 tokens and the example ConfigMap sets 65536 (`k8s/devops/configmap.example.yaml`). The raised caps of the planner fit 65536: the alternatives body is a quarter of it, and a refine tool answer of 8000 characters is about 2000 tokens.
- The verification slot (`ai.tasks.verification`) sets no window, so its default of 32768 tokens is below the 51000 tokens that its caps already allow (6000 for the body and 30 files of 1500). Raising them needs a configured window first, so they stay (see the table).
- The router of the LLM gateway ends a call at 1500 s (`router_settings.timeout` in `k8s/llm/gateway/config.yaml`). The new deadline of a model call (1200 s) stays under it, and a test holds this. A reply at the new output cap of 32000 tokens at 38 tokens per second takes about 840 s, plus 90 s for a cold read of the window: 930 s, under 1200 s. The model figures come from the measure of the longest call that the design of the output cap recorded.
- `DEFAULT_AI_IMPLEMENT_CONTEXT_WINDOW` is 128000. The step budget 64000 plus the turn reserve 40000 is 104000, inside it; a test holds this.
- The progress-based deadline (#3063) ends a Job whose log stays the same for the stall. The test `test_the_default_stall_covers_the_longest_wait_in_which_the_runner_writes_no_line` needs the stall to be above the longest of the three time limits by 600 s. With a watch of 3600 s, the stall must be at least 4200 s, and the extension at least the stall plus the delay of a row and a tick (571 s): 5400 s.

## Existing Tool Considered

No tool sets these limits. `pydantic-ai` (already used) takes the limits as `UsageLimits` and `ModelSettings`, and the settings layer (`Variable`, `Field`) already gives a variable to a setting. The change uses both and builds only the class table and its test. Cost: about 150000 tokens to build and to fix the tests that held the old numbers, 5000 tokens a year to keep the table, and about 6 hours. The change deletes five constants and the one place that read the old output cap.
