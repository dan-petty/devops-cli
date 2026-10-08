# Task: A GraphQL budget refusal pauses every roadmap Service worker until the reset, and each Service round ends with its spend line (#1400)

**Issue**: [#1400](https://github.com/dan-petty/devops-cli/issues/1400)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: P1-High (set by intake on 2026-10-08)
**Scope**: type/bug, scope/github

## Description

The machine account's 5,000-point GraphQL budget is shared by every repository worker in the roadmap Service. Before this change a budget refusal stopped only the round it hit: `RepoWorker._execute_batch` logged the error and the worker started its next round at the next trigger, while every other worker kept spending. On 2026-10-07 that was 34 refused rounds in 22 minutes across 8 repositories. Nothing reported a round's spend either: `GraphQLSpend.line` printed only from `devops roadmap` commands.

- **The refusal names its reset.** `require_budget`, `require_write_floor` and `require_floor` build their error with `_refusal`. It puts the budget's reset in the details under `CONST_GRAPHQL_REFUSAL_RESET_KEY` (`reset_at`), as ISO 8601 because `GitHubRateLimitError` turns every details value into a string. `refusal_reset(exc)` reads it back with `datetime.fromisoformat`, and returns None for any other error. The rate limiter's own errors never carry this key. They carry `reset_epoch`, or #1364's `reported_reset`, `local_clock`, `gap_seconds` or `reported_resources`, so none of them reads as a refusal.
- **A failed job keeps its reset.** `_execute_due_rows` still logs each failed job's traceback, and now collects the reset of each refused job. The `RoadmapRunError` it raises carries the earliest as `reset_at`, in the attribute and in its details. #1365's `ExceptionGroup` has not landed, so this is the field on `RoadmapRunError` the issue allows.
- **The engine stays generic.** `server/service.py` doesn't import the roadmap. `create_service_app` and `ServiceManager` take a `pause_until` reader (`PauseReader`, default `no_round_pause`), and `devops serve --service` passes `service_pause_until` from `roadmap/run.py`. That reader takes the reset from a `RoadmapRunError`'s `reset_at` or from a refusal raised outside any job (for example by `changes_since`). It adds #1364's `CONST_GH_RATE_LIMIT_CLOCK_SKEW_BOUND_SECONDS` (5 s). GitHub reported an ended window 0.72 s to 2.07 s past its reset (#1364), so the first round after the pause meets the new window rather than being refused with the old reset.
- **One pause for every worker.** `ServiceManager` holds one `RoundPause` and gives it to every `RepoWorker`. When a round fails, the worker passes the error to `RoundPause.after`, which compares and stores the time under the pause's own lock. A time that is not after the clock, or not after the time already held, changes nothing. A new time is held and logged once as INFO (`rounds_paused`, with the time and the repository whose round named it), so every worker refused for one reset produces one line.
  - While the clock is before the time, `_wait_for_next_batch` pops no batch. Triggers keep coalescing, and the worker re-checks on each notify and on its 0.2 s wait. Once the time passes, each repository runs one round holding every trigger that arrived meanwhile.
  - The job's error is still logged at ERROR, counted in `devops_cli_service_jobs_total{result="error"}`, and set on its span, as before.
  - The pause lives in the Service's memory, so a pod restart during a pause loses it. The new pod's start-up poll then runs a round, which a refusal pauses again.
- **A drain doesn't wait on held rounds.** `wait_active` waits only for a batch the pause lets run, so a rollout during a pause doesn't wait out the 120 s drain timeout. `drain_and_stop` joins each worker it stops within the drain timeout (`RepoWorker.join`), so the workers have ended when it returns, without running the held rounds. The next pod's start-up poll reads the changes they were for.
- **Each round ends with its spend line.** `service_job` wraps `run_due_jobs` in `try`/`finally` and calls `log_round_spend(repo, store)`. When the round's store sent a GraphQL request, that logs one INFO line naming the repository: "{repo}: GraphQL, {spent} of the account's points spent during the round, {remaining} left until {reset}.", with a since-the-reset variant (`GraphQLSpend.round_line`).
  - A round that a budget refusal ended makes no closing budget read. `graphql_spend(read=False)` builds the line from the last budget a response reported, which is the refusing one, so the pause starts without a paced extra GraphQL call.
  - Any failure of the closing read, of any class, logs a WARNING naming the repository, the class and the error. The round's own error is what the Service sees.
- **A pause that can't be read doesn't stop a worker.** When the reader fails, or its time can't be compared with the clock, `RoundPause.after` logs a WARNING naming the class (`rounds_pause_unread`), holds nothing, and the worker carries on.
- **No GraphQL, no budget query.** `GitHubRoadmapStore._run` records whether the store sent GraphQL, using the rate limiter's existing `gh_request_resource` classifier. `graphql_spend` returns None, and sends nothing, when it sent none. These texts say so, and `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md` and `docs/MCP_TOOLS.md` are regenerated:
  - the `RoadmapStore.graphql_spend` docstring;
  - the dry-run plans' closing budget read (`StoreRequests.budget`, condition "the run is done and sent a GraphQL request");
  - `devops roadmap close --plan`'s help and the MCP `roadmap_close` docstring, which end with the line "once its store has sent a GraphQL request". gh's own GraphQL, such as `gh pr checks` (#1415), doesn't count.

## Acceptance Criteria

- [x] `require_budget`, `require_floor` and `require_write_floor` put the reset time in the error's details, and the store's refused read carries the reset GraphQL reported (`test_each_refusal_carries_its_budgets_reset_in_its_details`).
- [x] The Service takes the earliest reset from a failed round:
  - from the error itself when the refusal comes from outside a job (`test_a_refused_read_of_the_changes_leaves_the_round_with_the_reset`);
  - from the failed jobs' refusals through `RoadmapRunError.reset_at`, while the next job still runs (`test_a_jobs_refused_write_fails_the_round_with_the_reset_and_the_next_job_still_runs`).
- [x] Only a refusal that carries a reset pauses (`test_an_error_that_is_not_a_budget_refusal_names_no_reset`, `test_an_error_that_names_no_reset_holds_no_round`). These hold nothing and log no wait:
  - a rate limiter error with only `reset_epoch`;
  - #1364's errors with `reported_reset`, `local_clock` and `gap_seconds`, or with `reported_resources`;
  - a job failure without a refusal, and any other error;
  - a refusal whose reset plus the bound has already passed (`test_a_refusal_whose_reset_has_passed_holds_no_round`);
  - a refusal whose time the reader can't read: a warning names the class and the worker runs its next round (`test_a_pause_reader_that_fails_holds_nothing_and_the_worker_carries_on`).
- [x] After such a round, `ServiceManager` starts no round for any repository before the reset plus the 5 s bound, for a refusal from `changes_since` and for a job's refused write (`test_a_budget_refusal_holds_every_repositorys_rounds_until_the_reset[changes_since]`, `[job]`).
  - Triggers arrive for both repositories 10 minutes before the reset and 4 s after it.
  - The wait is logged once with the time.
  - After it, each repository runs one round holding every trigger.
  - Two workers refused for one reset log one line, and the next hour's reset logs its own (`test_every_worker_refused_for_one_reset_logs_one_wait_line`).
- [x] A drain during a pause returns well within the drain timeout with the workers ended, and the held rounds never run (`test_a_drain_during_a_pause_stops_the_workers_without_running_the_held_rounds`).
- [x] Every round that sends a GraphQL request ends with a spend line naming the repository and saying the points are the account's.
  - A round that sends none logs no line and sends no budget query (`test_a_round_that_sends_graphql_ends_with_one_spend_line_naming_its_repository`, `test_a_round_that_sends_no_graphql_logs_no_spend_line_and_reads_no_budget`, `test_the_spend_reads_no_budget_until_the_store_sends_a_graphql_request`).
  - Through `service_job`, a refused round still ends with the line, from the refusing budget with no closing budget read, and raises the refusal unchanged (`test_a_service_round_ends_with_its_spend_line_however_it_ends`).
  - A closing read that fails with any class of error is a warning naming the class, and the round's own error stands (`test_a_budget_the_round_cant_read_is_a_warning_and_the_rounds_own_error_stands`).
- [x] `devops serve --service` passes the reader to the Service (`test_service_wiring`).
- [x] The dry-run plan of a close with no open release still matches a run that sends no GraphQL request (`test_a_close_with_no_open_release_sends_no_graphql_and_skips_its_plans_budget_read`).
- [x] Tests are offline. The service tests use an injected clock and injected jobs. The run tests use `GitHubFake` at the store's `runner` seam, with every interval job's schedule seeded, so no real `gh`, metrics or HTTP status read runs. Each new test's call phase stays under 1 s, and `uv run devops ci` passes.
- [x] `changelog.d/1400.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.
- Pending a person: once the Service runs a v0.2.29 image with this fix, check the next GraphQL refusal.
  - `{namespace="devops", container="service"} |= "No repository starts a Service round before"` shows one line per reset.
  - Take T0 as the epoch of that line and T1 as the epoch of the time it names. `max by (repo) (max_over_time(devops_cli_service_job_start_timestamp_seconds[<T1-T0>s] @ <T1>))` is below T0 for every repository, so no round started during the pause.
  - Failures of rounds already running when the pause began are expected and don't count.
- Pending a person: on the same rollout, `sum by (repo) (count_over_time({namespace="devops", container="service"} |= "of the account's points" | json [1h]))` is non-zero for every managed repository whose rounds read the board in that hour.

## Decisions and deviations

- **A field on `RoadmapRunError`, not an `ExceptionGroup`.** #1365 is open and in no milestone. When it lands, it moves this reset onto its group's `GitHubRateLimitError` members, as its key question says.
- **A new details key, not `reset_epoch`.** The rate limiter's `reset_epoch` also appears on its broken-state error, where it is a stale reset from the past. #1364's clock and missing-resource errors carry `reported_reset`, `local_clock`, `gap_seconds` and `reported_resources`. Only the three `require_*` functions set the new key, so none of those errors pauses anything. #1363's `RoadmapRefineError` is a `DevOpsCLIError`, not a `GitHubRateLimitError`, so a refine failure fails its job with no reset and pauses nothing.
- **The pause ends at the reset plus #1364's clock-skew bound.** It reuses #1364's `CONST_GH_RATE_LIMIT_CLOCK_SKEW_BOUND_SECONDS` (5 s), not its 1 s `CONST_GH_RATE_LIMIT_RESET_MARGIN_SECONDS`. The 1 s margin is shorter than the 0.72-2.07 s lag #1364 measured. A round resuming at the reset plus 1 s could be refused with the old reset, which `RoundPause.after` ignores as past, so each repository's first round would fail once. This item adds no constant of its own beyond the details key.
- **A refused round reads no budget for its line.** Its store already holds the refusing budget, so `graphql_spend(read=False)` reports from it. The line is the same, and the worker reaches `pause.after()` without waiting for a paced GraphQL call. The CLI's `_reporting_spend` still reads the closing budget after any run.
- **Best-effort steps catch every exception.** The closing budget read and the pause reader are best effort. Each catches `Exception`, logs a WARNING naming the class, and lets the round's own error stand and the worker carry on. Neither may hide the round's error or end a worker thread.
- **A reader injected into the engine.** The challenge noted that importing `RoadmapRunError` and `refusal_reset` into `server/service.py` would tie the generic engine to the roadmap. `PauseReader` keeps it generic, and the engine's tests only need an error to hand it.
- **The spend line comes from a helper.** `log_round_spend` takes the store, and is tested over `GitHubFake` the way `_github_round` does. The `service_job` tests seed the schedule of every interval job, metrics included, so the real metrics job never runs.
- **What counts as a round's GraphQL.** It is GraphQL the round's store sends, as `gh_request_resource` classifies it.
  - That classifier tests `'graphql' in arg` by substring, so a REST write whose body mentions GraphQL counts too. That errs toward logging a line, and the no-GraphQL tests use bodies without the word.
  - GraphQL that gh subcommands send outside the store, such as close's `gh pr checks` (#1415), counts in the account's points between the first and closing budgets, but doesn't cause a line by itself.
  - The spend keeps #1125's meaning: account-wide, from the first budget a response reported to the closing read, or to the refusing budget after a refusal.
- **Some refusals don't propagate.** Intake's refine hook and refine's visibility read log any exception and drop it, so a refusal there doesn't pause by itself. The round's next board read or write re-raises it, so the pause starts one call later. This is left as it is here.
- **A drain doesn't run held rounds.** This is a deliberate exception to the drain-runs-pending contract that `test_shutdown_drains_pending_delivery_enqueued_during_active_job` pins for rounds that may run. The drain now also joins each worker it stops, within the drain timeout.
- **The pause is in memory.** A pod restart during a pause loses it, and the new pod's start-up poll runs a round at once. That round is refused again if the budget is still low, which costs a probe point and restores the pause. Persisting the pause is not needed for that.
- **A reset already behind the clock pauses nothing.** If GitHub still reports the old window more than 5 s after its reset, that round fails and the next trigger runs a fresh round. Waiting again for a reset that has passed would hold nothing.

## Deliverables

- [x] `src/devops_cli/roadmap/board_read.py`: `_refusal`, the reset in the three refusals' details, `refusal_reset`, `GraphQLSpend.round_line`.
- [x] `src/devops_cli/exceptions/roadmap.py`: `RoadmapRunError.reset_at`.
- [x] `src/devops_cli/config/constants.py`: `CONST_GRAPHQL_REFUSAL_RESET_KEY`.
- [x] `src/devops_cli/roadmap/run.py`: the earliest reset of a round's refused jobs, `service_pause_until`, `log_round_spend`, and `service_job` ending with the spend line, with no closing budget read after a refusal.
- [x] `src/devops_cli/server/service.py`, `src/devops_cli/commands/serve.py`: `PauseReader`, `RoundPause` shared by every `RepoWorker` with its reader failures logged, the held batch in `_wait_for_next_batch` and `wait_active`, `RepoWorker.join` in the drain, and the reader wired into `devops serve --service`.
- [x] `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/request_plan.py`: no budget query from a store that sent no GraphQL, `graphql_spend(read=False)`, and the plans and docstrings to match.
- [x] `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/ai/mcp/server.py`: the wait line and its unread warning, the round's spend lines, the dry-run condition, and close's `--plan` and MCP texts. `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md` and `docs/MCP_TOOLS.md` are regenerated.
- [x] Tests: `tests/test_server_service.py`, `tests/test_roadmap_run.py`, `tests/test_roadmap_board_read.py`, `tests/test_roadmap_github_store.py`, `tests/test_roadmap_dry_runs.py`.
- [x] Changelog fragment: `changelog.d/1400.md`.
