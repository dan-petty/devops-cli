# Design

## Decisions

- **Use three lanes per repository**: The roadmap Service runs `status`, `triage`, and `model` lanes. Status runs metrics and implement. Triage runs intake. Model runs refine, stage, and alternatives. Each lane has an independent queue and worker. A slow refine round does not block intake.
- **Cross-lane refine trigger uses schedule.json stamp**: When intake places a P0 item, it writes a `refine_due` stamp to `schedule.json` under `_SCHEDULE_LOCK`. The model lane checks this stamp when judging whether refine is due. This allows cross-lane triggering without inter-thread coupling.
- **Direct devops roadmap run keeps same-round cross-job execution**: `devops roadmap run` evaluates all rows in `DEFAULT_DUE_TABLE` in a single pass. The `_refine_cross_job` predicate continues to trigger refine in the same round for CLI executions.
- **Triage task settings fall back to parent AIConfig**: `AITasksConfig.triage` defaults to an empty `AITaskOverride`. When unset, `ai.for_task("triage")` returns `ai.model`.

## Rejected Alternatives

- **Shared model lane with priority queue**: Keeping intake and refine in the same lane would still allow an in-progress refine call to block an incoming triage request for up to several minutes. Separate worker threads eliminate this delay completely.
- **In-memory event bus between workers**: Cross-lane notifications in memory would be lost on process restart or rollout. Stamping `schedule.json` persists state across restarts and reuses existing lock mechanisms.
