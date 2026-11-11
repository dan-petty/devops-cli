# Proposal: #4394

## Why

A step of the implement job stops at `roadmap.implement.step_token_budget` with the class `limit_reached`, also when it makes progress. In 14 days (2026-10-27 to 2026-11-10) 20 stops had this class, and a person finished 16 of them with a few commits on the branch of the run. One of them (#4004) needed 3.7% more tokens. In the last 20 tool calls before the stop, each of the 16 held at least 1 successful edit and at most 3 refused commands. The stops that repeated refused commands held 4 or more. A count of the last tool calls tells a step that makes progress from a step that spins. Closes #4394.

## What Changes

- A step that reaches its token budget, with no other budget spent, reads the digest of its last 20 tool calls from its own tool log (`ToolCallLog`): the successful edits (`write_file` and `edit_file` with the outcome ok) and the refused commands. With at least 1 edit and at most 3 refused commands, the budget grows one time by 50% (`CONST_ROADMAP_IMPLEMENT_EXTENSION_PERCENT`), up to a ceiling. The other rule numbers are constants in `config/constants.py` too.
- A missing digest (fewer than 20 calls), a digest that fails the rule, a ceiling that leaves no room and a second arrival at the limit stop the step as before. The reason gives the counts, or names the extension or the ceiling. The item budget and the time limits get no extension.
- New setting `roadmap.implement.step_token_ceiling` (default 16000000, twice the default step budget), with a variable. The settings refuse a ceiling below the step budget. Only a person sets it.
- The outcome of the step holds the extension. The record `implement.spend` keeps it for each step. The ready comment and the stop comment list each extension with its budgets and counts only. The Job log has one line for each extension.
- New counter `devops_cli_roadmap_implement_extension_total` with the label `decision` (`extended` or `halted`): 2 series.
- This is the decision point `implement.extension` of ADR 0020. Its resolver is the rule. The decision model stays unused: the rule makes no error on the labelled data, so a model has nothing to add. The registry of decision points (#4453) does not hold this point yet. The catalogue of ADR 0020 registers it after this change merges, in its own item, with the rule as its resolver, no model, and the constants as its data. Until then, `roadmap.decisions` does not control the point.
- The digest comes from the tool log of the step, not from `implement_trace.py`, which #4393 changes.
- The change fits one pull request.

How the item fits the halt-side items: #4043 (halt on consecutive refused commands), #4075 (halt when all tasks of the group are verified) and #4115 (stop early on stalls and refusals) stop a step before its budget. This item acts only at the budget, and only to go on. The items do not overlap: a step that a halt rule stops never reaches the budget, and this rule halts a step that spins at the budget as today.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: the ceiling setting, the stop at a budget with its one exception, the extension, the stop with no progress and the counter.
- `roadmap-implement-job`: the record and the comments show the extension.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_limits.py`, `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_extension.py`, `tests/roadmap/implement/test_roadmap_implement_job_extension.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md` and the generated `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/TELEMETRY.md`
- Cost of a run: an extended step can use up to 50% more input tokens, never above the ceiling or the item budget. On the 16 stops that a person finished, the extension replaces a stop, a person's commits and a retry.
- Metric series: 2.
- Operations: the live ConfigMap sets `roadmap.implement.step_token_budget` to 12000000, which is below the default ceiling, so the settings load. With that value the ceiling cuts the extension to 16000000. A person can set the budget back to the default after the merge.

## Feasibility

- Confirmed in the source: `StepBudget.spent()` in `implement_limits.py` is the one place that compares the input tokens of a step with `step_token_budget`, before each model request (`limit_hooks`). `ToolCallLog._note` in `implement_tool_log.py` sees every tool call of the step with its outcome (`ok`, `refused`, `retry`, `failed`), and a refusal of the shell has the outcome `refused`. So the digest needs no new evidence.
- Confirmed in the pilot 3 data (Loki runner log of 14 days, 36444 lines of 420 pods, and the job records of 77 items): the replay of the rule of this branch (`progress_digest` and `extends`) on the 20 stops with `limit_reached` extends each of the 16 that a person finished, extends 3 of 4 with no known end, and halts 1 (no edit). The stops of other classes that repeated refused commands halt. The replay is in a comment of the pull request.
- Confirmed against ADR 0020: it names the point `implement.extension` with a rule and a fallback, and no model.
- Confirmed that pydantic-ai's `FunctionModel` reports 50 input tokens for each streamed request, so the tests set a budget of 50 tokens.

## Existing Tool Considered

pydantic-ai `UsageLimits` is the open, maintained library that bounds a run. It stops hard at a limit and raises an error that holds a message and no field, so it has no rule to go on and the stop cannot name its setting (`implement_limits.py` already builds on `Hooks` for this reason). No open, maintained tool extends a token budget on progress. The change builds one pure rule function, one digest function and one setting on the existing `StepBudget` and `ToolCallLog`. Cost: about 150,000 input tokens and 25,000 output tokens to build, about 10,000 tokens each quarter to keep and fix it, and about 3 hours. The change deletes no internal code.
