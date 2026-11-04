# Design

## Decisions

- **Both the stage and the implement Job count with the tiktoken encoding that `devops_cli.ai.context_budget` selects, and both raise an error that names the missing cache when it is absent.**: One counter gives one measure. The character fallback is what makes the stage and the Job disagree.
- **A `creates` path carries a line estimate in `creates_lines`, and the stage adds 32 tokens for each estimated line.**: 32 tokens a line bounds dense code and markup, so a 1,500-line file counts as 48,000 tokens and fails a 40,000-token budget before the Job runs. The run's `budget` setting decides the budget that the stage and the prompt use.
- **The stage refuses a group that gives no line estimate for a `creates` path, and names the path.**: An unestimated file is an unmeasured group, which is the defect that the issue reports.
- **The staging tasks name the `budget` of the run and the line-estimate rule for each `creates` path.**: The planner sizes a group from the prompt, so the limit and the estimate rule have to be in it.

## Rejected alternatives

- **Keep the character fallback in both paths and state its error bound.**: `src/devops_cli/ai/context_budget.py` returns `max(1, math.ceil(len(text) / 4))`, whose count for dense code and JSON differs from the BPE count by more than any fixed margin, so the stage and the Job would still disagree.
- **Use the exact counter in the stage and the fallback in the Job.**: That is defect 1 of #3265: the stage passes a group that the Job later stops.
- **Estimate a created file at four characters a token.**: The heuristic at `src/devops_cli/ai/context_budget.py` undercounts dense code, so a 1,500-line file would count as about 15,000 tokens and pass the 40,000-token budget, which fails acceptance criterion 2.
