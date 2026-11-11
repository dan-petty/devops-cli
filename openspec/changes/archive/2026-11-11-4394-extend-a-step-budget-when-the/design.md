# Design

## Decisions

- **The rule is the resolver.** The decision point `implement.extension` (ADR 0020) has the chain rule, then fallback. The rule extends when the last 20 tool calls hold at least 1 successful edit and at most 3 refused commands. On pilot 3 each of the 16 stops that a person finished passes it (n=16, so the 95% upper bound of the error rate is about 19%). A decision model has no error to remove, so it stays unused, and no request goes to a model at the limit.
- **The numbers are constants.** `CONST_ROADMAP_IMPLEMENT_EXTENSION_CALLS` (20), `_MIN_EDITS` (1), `_MAX_REFUSED` (3) and `_PERCENT` (50) are in `config/constants.py` with the data that gave them. ADR 0020 keeps the parameters of a rule as data; the registry of decision points (#4453) takes them over when a later item registers the point, as the catalogue of ADR 0020 says. A person changes the cost of an extension with the ceiling, which is a setting.
- **One extension of half the budget.** One stop needed 3.7% more tokens, and the others were finished by a person, so the need of a step is not known. Half of the budget gives room for a step that is further from its end, and the ceiling and the item budget bound the cost. A second arrival at the limit stops the step.
- **The ceiling is a setting.** `step_token_ceiling` defaults to twice the default step budget (16000000) and must not be below the step budget. The ceiling follows the deadline ceiling of the Job (`deadline_ceiling_seconds`): a fixed value that only a person changes.
- **The digest comes from the tool log of the step.** `ToolCallLog` keeps the tool name and the outcome of its last 20 calls in a bounded deque, over all turns and tiers of the step. `progress_digest` is a pure function of that list. The trace (`implement_trace.py`) is not read: #4393 changes it, and its events drop when the trace is long.
- **The decision happens once at each limit.** `StepBudget` keeps the reason of a halt, so a repair turn that checks the budget again gets the same reason and the counter counts no second decision. When another budget is spent at the same time, the step stops as before and the rule does not run.
- **The record holds counts only.** The extension in the outcome, the record `implement.spend` and the comments holds the two budgets, the counts and the ceiling flag. No path, command or text of the model.

## Rejected alternatives

- **A Jev decision step.** ADR 0019 and ADR 0020 add a model only where it adds to the best rule. The rule has no error on the 33 labelled checkpoints of pilot 3, so a model adds cost and latency and nothing measurable.
- **Settings for the window, the counts and the share** (the refine proposal). The task of this item asks for a fixed share in `config/constants.py`, and ADR 0020 puts the parameters of a rule in the data of its point. Four new settings would make an untested rule easy to change in the ConfigMap. The ceiling is the setting a person needs.
- **A share of 10%.** It covers the one measured need (3.7%) but not a step that is further from its end; the pilot 3 data has no other measured need.
- **Halt when the last 20 calls hold no successful edit.** Pilot 3 found that it is a bad halt rule, so the window gates only the extension and stops nothing early. This item adds no halt rule; #4043, #4075 and #4115 own the halt side.
- **Count any changed log line as progress** (the deadline rule of the Service). A refused command also writes a line, so a step that only refuses calls would extend.
- **Read the digest from `implement_trace.py`.** #4393 changes that module in an open pull request, and the trace drops old events when it is long.
