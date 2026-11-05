# Proposal

## Why

Issue #3568, part 1 of #3053: a step of the implement job that fails stops the item. The repair rounds that exist today (`roadmap.implement.repair_rounds`) cover a failed `ruff`, `mypy` or hook and a missing tick. Nothing else bounds the work of a step. A step has no limit on tokens or on time, so one step can spend 10 million input tokens before it stops (#2554), and a stop names no limit. The trace shows model calls, tool calls and checks, but not the attempts: a reader cannot see that the second attempt passed.

This change is part 1 of the issue. It gives a step and an item their budgets, makes each stop name the limit that ended it, holds that a failure that no attempt can fix gets no repair round, and records each attempt in the trace. The rest of the issue (a strategy for each round, the guard against a repeated failed action, the smaller edit for a `parser` failure, the reset of a moved HEAD, the no-op group, and the repair of a failed verification command) is filed as sub-issues of #3053 (#3569, #3570, #3571, #3575, #3576 and #3577).

## What Changes

- Four settings in `roadmap.implement`: `step_token_budget` (default 8,000,000 input tokens), `item_token_budget` (default 20,000,000), `step_time_limit_seconds` (default 5400) and `item_time_limit_seconds` (default 12600). Each has an environment variable. `item_time_limit_seconds` must not be above `deadline_ceiling_seconds`, so the named stop comes before the end of the Job by its deadline.
- A new module `src/devops_cli/roadmap/implement_limits.py` holds `StepBudget` and the capability `limit_hooks`. Before each model request, the capability checks the four limits and raises `LimitReached` when one is spent. It adds the input tokens of each reply to the spend of the step. `run_step` and `run_fix_step` take what the item spent before the step (`ItemSpend`).
- A new failure class `limit_reached` with the default action `raise_limit`. Its stop reason names the setting and its value, for example `roadmap.implement.step_token_budget=8000000`.
- A step that uses all its repair rounds adds a line to its reason that names `roadmap.implement.repair_rounds` and its value.
- A failure of class `plan_defect` or `premise_false` gets no repair round. Only a failed static check or hook, and a missing tick, get one, so the code needs no new rule. A test holds this, and the trace shows the single attempt.
- A new trace event `attempt`: the number, the tier, the outcome, the failure class, the evidence and whether a repair round follows. `devops roadmap explain --trace` prints it.
- The change carries spec deltas in `roadmap-implement-step`, `roadmap-failure-taxonomy` and `roadmap-explain`, because the settings, the stop reason, the class and the trace line are observable.
- The change fits one pull request. #3053 is split into sub-issues, and this change delivers #3568. The other sub-issues finish #3053.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: the budgets, the named stops, the fatal classes and the attempt events
- `roadmap-failure-taxonomy`: the class `limit_reached` and its action
- `roadmap-explain`: the trace line of an attempt

## Impact

- Code: `src/devops_cli/roadmap/implement_limits.py` (new), `implement_step.py`, `implement_run.py`, `implement_trace.py`, `explain.py`, `failure.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_implement_limits.py` (new), `tests/roadmap/test_roadmap_implement_step_attempts.py` (new), and the tests of the failure classes, the limit classes and the trace
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, and the generated `docs/ENV_VARS.md` and `docs/CONFIGURATION.md`
- The budgets count the input tokens that the model replies report, as a run of the Job. A new Job after a stop starts a new count.

## Dependencies

#3054 (keep work and resume) is merged. #3098 (partial implementations) builds on this change and on the follow-up items.

## Feasibility

Checked on `origin/main` b82fe605, on 2026-11-05.

1. The gap is real. `git grep -n "token_budget\|time_limit" -- src/devops_cli/config src/devops_cli/roadmap` found no budget of tokens or time for a step. `repair_rounds` exists and bounds the extra turns of a step. The stop of `_attempt` names no limit.
2. The default of the issue does not fit the data. The proposal of the issue sets 300,000 input tokens for a step. The tables of the pull request comments and of the stop comments show done steps at 580,448, 865,790, 1,033,394, 2,011,925, 2,034,138, 2,693,955, 2,878,517 and 5,858,291 input tokens (#3106, #3394, #3442, #2570), and stopped steps at 7.2 to 10.5 million (#2636, #2570, #2554). A step runs up to 500 requests, and each request sends the whole conversation, so the sum is large. A limit of 300,000 would stop every step that works today. The default is 8,000,000: above the largest done step, below the runaway stops. The default of the item is 20,000,000: the largest item that finished its steps used 16.6 million (#2570). These defaults are a first bound and a person can change them.
3. pydantic-ai gives `UsageLimits(input_tokens_limit=...)`, but its error holds a message and no field, so a stop could not name the setting without a text match. The `Hooks` capability gives the typed value `RunContext.usage` and the `response.usage` of each reply. The step already uses `Hooks` for the output cap (`implement_output_cap.py`). So the limits are a hook of the same kind.
4. The time limit is not in pydantic-ai: `UsageLimits` has no wall-clock limit. The hook checks the clock before each request. A running command has its own limit (`command_timeout_seconds`), and a model call has its own (`request_timeout_seconds`).
5. The trace already has the kinds `model`, `tool`, `check` and `retry`. A reader can rebuild an attempt from them, but not its class. The `attempt` event adds the class and the evidence at the point where the step knows them.

Not verified: a real model run on a pod. The tests replay the steps with a scripted model, a real git repository and faked process edges.

## Existing Tool Considered

pydantic/pydantic-ai (MIT, maintained) covers bounded retries, `UsageLimits` for requests, tokens and tool calls, and `ModelRetry` for a failure that goes back to the model. The step already uses `UsageLimits` for the request and tool-call limits. It lacks a limit on the wall-clock time of a step, a limit for the whole item, a stop that names a setting, and a failure class. This change builds those parts as one 120-line module on the `Hooks` capability that the step already uses. It deletes no internal code.

Cost to build: about 90,000 tokens (the module, the settings, the class, the trace event, two test files and the documents) and about 5 hours with two CI runs. Cost to keep: about 4,000 tokens each quarter. Cost to fix one miss: about 10,000 tokens.
