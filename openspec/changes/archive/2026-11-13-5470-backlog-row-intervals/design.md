# Design

## Decisions

1. **The settings live in the section of each row.** `RowCadenceConfig` holds `interval_minutes`, `backlog_interval_minutes` and `backlog_threshold`, and its check that the backlog interval is not above the interval. The sections `roadmap.intake`, `roadmap.stage`, `roadmap.fix_plan`, `roadmap.refine` and `roadmap.alternatives` extend it, and each sets the default of `interval_minutes` to the old constant. A variable sets each field, such as `DEVOPS_CLI_ROADMAP_STAGE_BACKLOG_THRESHOLD`.
2. **The rule is off by default.** `backlog_interval_minutes` and `backlog_threshold` are empty by default. The rule applies only when both have a value. So the release changes no interval until a person sets the values.
3. **The runner gives the queue.** `JobOutcome.queue` holds the size of the queue that the runner counted from the listing that its round read, or None when the runner read no listing (`roadmap.fix_plan.mode` is `off`, or the alternatives check is off). The queue of each row:
   - `intake`: the candidates of the round: the decided, the left and the held ones.
   - `stage`: the open items that the stage filter names (`StageSelection.queue`), before the rules of each item and the limit.
   - `fix_plan`: the open pull requests of the listing that hold `plan/needs-fix` (`RoadmapStore.labelled_pulls`).
   - `refine`: the items that the selection orders, before the rules of each item and the limit (`RefinePlan.queue`).
   - `alternatives`: `Coverage.unchecked`, the items that the check can take and has not checked.
4. **The next round reads the last queue.** The round decides which rows are due before any row runs, so it uses the queue that the last round of the row recorded. The round writes the queue to `queues.json` beside `schedule.json` when the row succeeds. A failed round, and a runner that gives None, keep the last record.
5. **The round reads the settings at each round.** `run_due_jobs` reads `roadmap` from `load_settings()` once for a round when a row of its table has a cadence. The status lane has no such row and reads nothing more.
6. **One log line and two gauges for each run.** After a row with a cadence succeeds and gives its queue, the round logs `MESSAGES.roadmap.run_row_queue` (or `run_row_queue_backlog` while the rule applies) with the row, the repository, the queue and the minutes, and sends `devops_cli_roadmap_row_queue_items` and `devops_cli_roadmap_row_interval_seconds`. One repository adds at most 10 series: 5 rows and 2 gauges.
7. **The model lane stays serial.** The model lane runs `retitle`, `stage`, `fix_plan`, `refine` and `alternatives` one after the other, and a stage round of 3 items can take more than one hour. A shorter loop makes a row due at more rounds of the lane, but each round runs each due row once, in order, so a short refine loop does not run refine during a long stage round. Until #4559 moves stage to Jobs, the rounds per hour of refine rise only when the stage rounds are short. `roadmap.stage.jobs` of #4559 is the parallel lever for stage.
8. **The overlap with #4559.** #4559 changes the stage row in `run.py`. This change edits the stage adapter in one place only: it puts `plan.queue` in the outcome. The other edits are in the due logic. The second pull request to merge rebases and keeps the queue in the outcome of the new stage row.

## Rejected alternatives

- **Count the queue in `run.py` with a new read of the store.** Refine reads the backlog listing with `store.backlog()`, which the store does not keep: a second read costs one request for each 100 open items, 6 or more requests for 583 New items in each round. The issue asks for the count from the listing that the round already reads.
- **Keep the queue in memory.** The Service restarted 71 times in one week (#4559). A queue in memory is lost at each restart, so the row uses the long interval until its next round.
- **Count the items that the rules of each item keep.** The stage selection stops at its limit and reads the git holders and the blockers of each item it judges. To count the items that pass every rule, the round must judge all 177 Ready items, with more reads. The count of the items that the filter names is the number that the issue gives (Ready 177, New 583).
- **A floor from the time limits of a step.** The interval is no time limit (proposal, Feasibility). A floor gives no protection and blocks a short loop for `fix_plan`, whose time budget (3600 s) is above its default interval (53 minutes).
- **A backlog interval above the interval.** A larger interval for a larger queue is the opposite of the request, so the settings refuse it.
