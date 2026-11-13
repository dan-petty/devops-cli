# Proposal: #5470

## Why
The owner asked to make the loops of the roadmap jobs with a large backlog shorter (#5470). On 2026-11-13 at 17:20Z, 177 items were Ready (the queue of `stage`) and 583 items were New (the queue of `refine`). In 24 hours, stage made 11 attempts and refine gave 55 results, so the stage queue alone was about 16 weeks of work.

The interval of each row of the Service was a constant in `src/devops_cli/roadmap/run.py`. A person could not make a loop shorter without a release, and a row ran at the same interval with 0 or 500 items in its queue.

## What Changes
- The rows `intake`, `stage`, `fix_plan`, `refine` and `alternatives` read their interval from settings at each round: `roadmap.<row>.interval_minutes`. The default of each setting is the value of the old constant: 29, 37, 53, 17 and 719 minutes. The new section `roadmap.refine` holds the settings of the refine row.
- Each of these rows has a backlog rule: `roadmap.<row>.backlog_interval_minutes` and `roadmap.<row>.backlog_threshold`. While the last queue of the row holds the threshold or more items, the row is due at the backlog interval. Both settings are empty by default, so the rule is off until a person sets them. The settings refuse a backlog interval above the interval.
- The runner of each row gives the size of its queue from the listing that its round reads, with no new request: the open items that the stage filter names, the items that refine can take, the candidates of intake, the open plan pull requests with `plan/needs-fix`, and the items that the alternatives check can take and has not checked.
- The round keeps the last queue of each row in `queues.json` beside `schedule.json`, so a restart keeps the rule. A record that exists and cannot be read stops the round and names the file, as `schedule.json` does.
- Each round that runs one of these rows logs one line with the queue and the interval in use, and sends the gauges `devops_cli_roadmap_row_queue_items` and `devops_cli_roadmap_row_interval_seconds` by `repo` and `row`.
- The self-cap of the Service on GitHub requests (`service.github_requests_per_hour`) stays. Each request of a shorter loop goes through the same gate.
- The change adds settings and changes when the Service runs a row, so it has a spec delta.

## Capabilities
- New: `roadmap-row-cadence`. It holds the settings of the cadence of a row, the backlog rule, the queue of each row, its record, its log line and its gauges.

## Impact
- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/run.py`, the selection of stage (`stage/stage.py`) and of refine (`refine/refine.py`), the store (`stores/store.py`, `stores/github_store.py`), `src/devops_cli/telemetry/instruments.py` and the messages.
- Documents: `docs/CLUSTER.md`, the help of `devops roadmap run`, and the generated `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/TELEMETRY.md` and settings reference.
- The live ConfigMap is not in git. After the release, a person sets the values in it. The issue proposes: stage 13 minutes at 50 or more Ready items, refine 7 minutes at 100 or more New items, fix_plan 23 minutes at 3 or more plans with `plan/needs-fix`, and alternatives 181 minutes at 50 or more unchecked items.
- The model lane runs its rows one at a time. Until #4559 moves stage to Jobs, a long stage round delays the other rows of the lane, also when their loops are shorter (design.md, decision 7).
- #4559 changes the stage row of `run.py` in parallel. This change keeps its edit of the stage adapter to one line, the queue in the outcome. The second pull request to merge rebases on the first.
- The change fits one pull request.

## Feasibility
- `src/devops_cli/roadmap/run.py` at `origin/main` (94a1999ea): each row of the due table sets `interval=timedelta(minutes=DEFAULT_ROADMAP_<ROW>_INTERVAL_MINUTES)`, and `_is_interval_due` compares it with the last success. No setting reads it.
- `load_settings` reads a config file again when its stamp changes (`_config_layers` in `src/devops_cli/config/settings.py`). `k8s/devops/roadmap-service/deployment.yaml` mounts the ConfigMap `devops-cli-config` as a directory at `/config` with no `subPath`, so the kubelet updates the file and the next round reads the new value with no restart. The row `fix_plan` already reads `roadmap.fix_plan.mode` this way at each round.
- The GitHub store reads the listing of every issue once for a round and keeps it (`GitHubRoadmapStore._every_issue`, field `_all`). The listing holds pull requests with their labels (`IssueRecord.pull_request`, `IssueRecord.labels`). Stage reads it through `store.items()` in `_open_items`, and the step fix-plan through `store.items()` in `_candidates`. Refine orders its items from the milestone and backlog listings in `select_candidates`, intake reads `store.issues()` in `plan_intake`, and the alternatives check counts `Coverage.unchecked` in `select_items`. So each runner can give its queue with no new request.
- Each GitHub request of the Service goes through the gate of `RequestBudget` (`set_request_gate` in `src/devops_cli/github/rate_limiter.py`, setting `service.github_requests_per_hour`, default 500). A request that the last hour has no room for waits. So a shorter loop cannot send more than the budget.
- The issue asks that a row interval is never below the longest time limit of a tool or a step of its round. This premise does not apply: the interval is the time between the starts of two rounds of a row, not a time limit. A lane runs its rows one at a time (`_execute_due_rows`), so a row never overlaps itself. A round that runs longer than the interval makes the row due at the next round of the lane, and each time limit of the round stays inside the round. So the change adds no floor from a step limit. The floor of each setting is 1 minute, and the poll tick (`service.poll_interval_seconds`, 151 s by default) is the real lower bound.

## Existing Tool Considered
pydantic-settings, the settings library of the project, holds the new settings, and the existing due table of `run.py` holds the rule. A queue-driven autoscaler such as KEDA scales pods, not the interval of a row in one pod, and ADR 0021 rejects it for the engine phase in favor of Argo semaphores. The issue estimates the cost to build at 0.3 M tokens and 2 hours. The change deletes no internal code: the constants `DEFAULT_ROADMAP_<ROW>_INTERVAL_MINUTES` of the five rows stay as the defaults of the settings, and the field `JobRow.interval` stays for the rows with a fixed interval.
