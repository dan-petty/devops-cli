# roadmap-eval-funnel Specification

## Purpose

Report end-to-end roadmap item conversion by ISO-week cohort and delivery path (`G1` vs `continue`) from GitHub issue timeline events and Loki result lines via `devops roadmap eval funnel`.

## Requirements

### Requirement: Cohort of one ISO week

`devops roadmap eval funnel` SHALL group items into cohorts by the ISO week (`YYYY-Www`) of each item's latest `status/ready` label event at or after `--since`. An `unlabeled` `status/ready` event SHALL cancel an earlier `status/ready` event when the item leaves `Ready` without progressing to a forward status label (`status/planned`, `status/in-progress`, `status/in-review`, `status/blocked`).

#### Scenario: An item ready twice counts once

- **WHEN** an issue timeline records `status/ready` in ISO week 45, an `unlabeled` event of `status/ready`, and a second `status/ready` in ISO week 47, and the command runs with `--since` before week 45
- **THEN** the item appears once in cohort `YYYY-W47` and does not appear in `YYYY-W45`

### Requirement: Step path of each item

The funnel report SHALL assign path `continue` when an item's delivery PR shares its plan PR's head branch, and `G1` when branches differ or a merged plan PR precedes delivery. Both paths SHALL report `New (placed) to Ready` and `Ready to plan PR open`; `G1` adds `plan PR merged to ready delivery PR` and `ready delivery PR to merge`; `continue` adds `plan PR open to ready delivery PR` and `ready delivery PR to merge`.

#### Scenario: An item on the continue path

- **WHEN** an item timeline holds a plan pull request on branch `docs/openspec/5494-eval-funnel` and a delivery pull request on the same branch
- **THEN** the item counts in `continue` step `plan PR open to ready delivery PR` and not in `G1` step `plan PR merged to ready delivery PR`

### Requirement: Measures of each step

For every step in a cohort, the report SHALL output `n`, pass `share`, the Wilson 95% confidence interval via `wilson_interval`, the smallest change `n` can separate (half-width `(upper - lower) / 2`), and the median and `p90` durations of passed items in that cohort step.

#### Scenario: Known pass share gives known bounds

- **WHEN** a step records 8 passes in 10 completed items
- **THEN** the step reports `n=10`, `share=0.8`, Wilson bounds `0.490` and `0.943` within `0.001`, smallest change `0.227` within `0.001`, and the median and `p90` pass durations

### Requirement: An item younger than the p90 time

An item still in a step whose elapsed age is strictly less than the window-wide `p90` pass duration of that step SHALL count as `in progress`, excluded from `n` and `share`.

#### Scenario: A young item is in progress

- **WHEN** an open item remains in `Ready to plan PR open` with an age below that step's window `p90` pass duration
- **THEN** the item increments `in_progress` and does not count as a failure in `n` or `share`

### Requirement: Tokens and cost for each success

The command SHALL query Loki instant metrics over `RESULT_LINES` for `tokens`, `cost_usd_micros`, and line counts per `(repo, roadmap_job, item)`. Each step SHALL divide the cohort's summed totals by its pass count, each item SHALL report `New` to `staged` tokens (`0` when absent), and missing-line items SHALL stay in `n` with `0` totals and be counted.

#### Scenario: An item with no result line

- **WHEN** Loki returns `tokens=1000` and `cost_usd_micros=2000` for 2 of 3 cohort items and no lines for the third item
- **THEN** the third item remains in `n` with `0` tokens, each step's per-success metrics divide the summed cohort totals by the step's pass count, and the output states `1` item with no result line

### Requirement: Paced GitHub reads, option validation, JSON output, and dry-run

`devops roadmap eval funnel --since <date> [--repo <owner/name>] [--loki-url <url>] [--json] [--dry-run]` SHALL validate `--since`, `--repo`, and `service.repos` before sending any HTTP request, read GitHub via the paced `GitHubSession`, emit structured JSON with `--json`, and send 0 requests while printing its planned GitHub and Loki requests under `--dry-run`.

#### Scenario: The dry run sends no request

- **WHEN** a user runs `devops roadmap eval funnel --since 2026-11-01 --repo example/app --dry-run`
- **THEN** the command exits 0, sends 0 HTTP requests, and prints the planned GitHub and Loki queries
