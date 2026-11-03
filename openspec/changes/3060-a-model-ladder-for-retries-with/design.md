# Design

## Decisions

- **Store the ladder as `roadmap.implement.ladder: dict[str, list[str]]` in `RoadmapImplementConfig`.**: `RoadmapImplementConfig` configures implement settings, supports setting variables, and prints in `devops config show`.
- **Default the ladder to the local `devops-coder` group of each class.** `SECURITY.md` item 13 states a prompt leaves the cluster only when a caller explicitly names a hosted group. One tier keeps a run that sets no ladder on its current model; a person adds `devops-reasoning` after the first tier for a stronger second attempt.
- **Advance the ladder on `FailureAction.CHANGE_TIER` without incrementing repair rounds.** The failure taxonomy maps `FailureClass.PARSER` to `CHANGE_TIER`. A run that ends on a provider error also moves down the ladder, as a provider outage is the same signal. Changing tiers addresses model defects without wasting code repair turns.
- **Rebuild the step agent per attempt with the model of that tier and the context window of the task.** The inputs of a step are measured against the task window before the first attempt, so every tier must accept them. The CLI has no per-tier window to read, and the conservative task window keeps every tier under its own limit.
- **Record the tier in `StepOutcome` and itemize spend per tier under `implement.spend`.**: The run record maintains `implement.spend` per item. Itemizing by tier enables spend tracking and cost audit.
- **Check gateway tier health before each attempt and skip unhealthy tiers.**: Probing health before an attempt prevents sending requests to offline backend pods.

## Rejected alternatives

- **A single global tier list across all step classes.**: Planning steps need large context windows for codebase exploration, while repair steps need specialized reasoning models for syntax fixing. A single list either over-spends on edits or starves repair steps.
- **Spend a repair round on parser errors.**: Issue #2953 proved that a model family with an XML tool-call bug repeats the exact same error on subsequent repair turns. Spending repair rounds on model bugs exhausts the repair budget without fixing code.
- **Cache gateway tier health with a TTL.**: `src/devops_cli/ai/gateway.py` has no per-group health endpoint, and backend pods can fail within the 1500s request timeout window. A TTL cache returns stale healthy status during outages.
- **Record aggregate token totals only.**: `docs/ROADMAP_WORKFLOW.md` and `devops ai spend` evaluate model cost efficiency. Without per-tier spend attribution in the run record, operators cannot measure the cost impact of tier escalations.
