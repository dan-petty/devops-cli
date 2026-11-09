# Design

## Decisions

- **Source facts dynamically from repository files at the staged commit**: Read `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/runner_tools.py`, `Dockerfile`, and `k8s/devops/cronjob-runner.yaml`. Fail the context builder when any source file moves or is missing.
- **Trigger context inclusion by keywords**: Include the failure taxonomy when item text or draft cites retry, review, stop, tier, or failure words. Include runner capabilities when text cites a command or tool name. Keep both out otherwise to conserve tokens.
- **Instruct the planner in `roadmap_stage_change.md`**: Instruct the planner to state needed failure classes and runner capabilities in `## Feasibility` with one line per needed capability naming the program, its source in image or `NOT_IN_RUNNER`, and applicable pod security settings.
- **Enforce runner capability gate in `content_problems`**: Check whether a plan adds `devops review` to the Job or runs a verify program from `NOT_IN_RUNNER`. Require `proposal.feasibility` to name the capability; refuse the plan with an informative message otherwise.
- **Check every staged plan regardless of effort**: Staging runs before the Service effort filter, so the gate protects every plan.
- **Use PR #3183 as the golden set replay case**: Add `3183-the-implement-job-reviews-its-own` to `tests/fixtures/roadmap_eval/stage/` with a defect expecting the refusal for missing runner capability on `devops review`.

## Rejected alternatives

- **Copy static class tables and capability lists into the prompt**: This drifts when underlying code changes and fails the source-move contract.
- **Always include failure and runner capability facts**: This spends unnecessary tokens on plans that do not touch commands or failure behavior.
- **Search the whole plan for tool names**: This causes false refusals when a plan mentions a tool in prose or a citation.
- **Add a new label for refused plans**: Existing `owner/*` claim labels already indicate item state and carry the reason.
