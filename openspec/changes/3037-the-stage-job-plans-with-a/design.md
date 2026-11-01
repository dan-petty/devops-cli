# Design

## Decisions

- **Use a git worktree on the staged commit for the sandbox.**: ADR 0005 states tools run on a worktree of the reviewed commit. A worktree supports git log and git show. It is lighter than a full clone.
- **Set the default budget to 30 tool calls and 50,000 tokens, configurable.**: A token cap alone does not stop a loop of cheap calls. The call count cap bounds round-trips. The values are larger than the current fixed context so the agent can investigate more.
- **Store the trace in the job record alongside the plan output.**: The Service already stores job records. One place to find the run record. Consistent with the implement job pattern.
- **The planner has no write tool and no network tool.**: The sandbox enforces this. ADR 0005 states the sandbox has no network. The planner only reads.
- **The planner writes evidence into the Feasibility section of the plan.**: AGENTS.md requires Feasibility to name how the premise was confirmed. The tool calls and their output are the evidence.

## Rejected alternatives

- **Use git clone --local for the sandbox.**: Heavier than a worktree. Creates a full copy. No advantage over a worktree for read-only access.
- **Use git archive to a directory.**: No git history. Cannot run git log or git show.
- **Use an unbounded call count with only a token cap.**: A token cap alone does not stop a loop of cheap calls. The call count cap is needed to bound round-trips.
- **Store the trace in a separate file in the change folder.**: Two places to look. The change folder is for the plan, not the run record.
- **Store the trace as an issue comment.**: Too verbose for a trace. Pollutes the issue history.
