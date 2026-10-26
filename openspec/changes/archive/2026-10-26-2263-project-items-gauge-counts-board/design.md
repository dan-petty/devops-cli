# Design

## Source of the counts

`store.items()` reads the board (GraphQL pages of 100 cards) and the issues of the repository (REST), and joins them by issue number. An issue that is not on the board has no card, so it is not an item. The roadmap Service opens its store with an empty board filter, so the read holds open and closed items.

One read costs one budget query plus one GraphQL page for each 100 cards: 12 pages, so 12 points by `read_cost`, for 1,170 cards, every 15 minutes. The read refuses before it spends when the budget is below the floor, as for each other board read.

## Labels

| Label | Value |
| :--- | :--- |
| `milestone` | The milestone title, or empty. |
| `state` | `open` or `closed`, the state of the issue. |
| `type` | The `type/*` label of the issue without its prefix, or empty. |
| `priority` | The board Priority, or empty. |

An empty label value is the same as no label for Prometheus. A query that groups by `milestone` returns the items with no milestone as a series without that label.

## Vanished label sets

The tracer flushes gauges with DELTA temporality, so a series that is not set in a round is not sent. Prometheus keeps its last sample for `last_over_time(...[$__range])`. An item that moves from `In Progress` to closed leaves its label set, and the panels would count it in both.

`emit_project_metrics_telemetry` keeps the label sets that it sent in the last snapshot (`_sent_item_series`, reset by `reset_sent_item_series`). It sends 0 once for each set that is not in the new snapshot. A new process starts with no sent sets, so the sets of an earlier process keep their last value until they leave the time range of the panel.

The in-memory registry that Prometheus scrapes is cleared and written again at each snapshot, so it needs no 0.

## Rejected alternatives

- **Send all combinations of the known values.** 51 milestones, 2 states, 8 types and 5 priorities are about 4,000 series at each flush, nearly all 0, for a board of 1,170 items. Rejected: most series would carry no information.
- **Make the panels read the newest sample only.** This needs the time of each sample in the query. On the cluster's Prometheus, `time() - timestamp(last_over_time(devops_cli_project_items{state="closed"}[30d]))` is 0 for every series, although the samples are a day old, so `last_over_time` reports the evaluation time and not the sample time. Also, `project-metrics-dashboard` requires `last_over_time(<metric>[$__range])` for each gauge panel.
- **Use the board Status as `state`.** The panel description and the existing values say open and closed, and the acceptance criterion compares the open count. The Status stays on the board. A label for it would multiply the series, and no panel reads it.
- **Keep the milestone-only counts and add the missing item in no milestone.** The description of the instrument names type and priority, and the issue asks for them. Rejected: it leaves the gauge and its description in disagreement.
- **Log a warning and send no items when the board read fails.** A failed read then looks like an empty board, and the 0 rule would send 0 for every label set. The read raises. The Service wraps the whole collection in its existing handler, which logs the failure.
