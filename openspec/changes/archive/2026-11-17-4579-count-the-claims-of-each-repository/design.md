# Design

## Decisions

- **Count the claimants inside `get_item_age_metrics` and return them beside the ages.**: The read of the items happens there once. A failed read of the label events then sends neither the ages nor the claims, and the snapshot adds no GitHub request.
- **Name the label `claimant`, with the values `service`, `agent` and `human`.**: `owner` means the GitHub owner and the `owner/*` label family in this repository, so the label takes the claim word in lower case.
- **Send 0 for a kind that holds no open item, each round.**: The three kinds are a closed set, so a sample of 0 keeps the series current and the gauge needs no memory of the last snapshot.
- **Reuse the existing report and emission path.**: `ProjectMetricsReport.claims` and `_emit_item_ages` follow the item ages, so the metrics row needs no new row or setting.

## Rejected alternatives

- **Name the claim label `owner`.**: It is ambiguous with the GitHub owner.
- **Reuse the `_sent_item_series` memory.**: That memory serves `PROJECT_ITEMS`, whose labels form an open set. The claimant kinds are a closed set.
- **Read the items again for the counts.**: The acceptance criteria forbid an extra GitHub request, and a second read can send one.
- **Emit the items gauge here.**: The owner decision of 2026-11-13 moves it to #5495.
- **Build the pipeline dashboard panel.**: #3655 owns the panel, and no test of this repository can check a panel offline.
