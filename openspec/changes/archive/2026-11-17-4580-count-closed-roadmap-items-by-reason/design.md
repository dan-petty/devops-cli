# Design

## Decisions

- **Count in `_route`, after the duplicate check and before `_hand_to_consumers`.**: The count then sees each delivery once, and it sees the closes that the roadmap jobs make, which the consumer refuses as the App bot's own write.
- **Read the labels and the `state_reason` from the signed payload.**: The delivery already carries the issue, so the count costs no GitHub request and no rate-limit budget.
- **Match the `priority/` prefix to tell a roadmap item from a candidate.**: An item is an issue with a `priority/*` label (`CONTEXT.md`, ADR 0001).
- **Use `unknown` for a close that GitHub gives no reason for, or another value.**: The reason stays a bounded set, because a raw `state_reason` is text that GitHub chooses.
- **Prime at zero through `GLOBAL_METRICS.prime_counter` in `create_webhook_router`.**: It follows `devops_cli_service_webhook_deliveries_total`, and the row test requires each Service counter to have a panel.
- **Add the panel to the row "Roadmap Service".**: The project records that every Service series is charted in that row, and the row test fails on a counter with no panel.

## Rejected alternatives

- **Count in the roadmap consumer `deliver`.**: The consumer refuses the App bot's own writes, so the items that the jobs close would not count.
- **Count in the scoped update.**: A scoped update runs only for some events and after the listing snapshot, so it misses closes and costs a store read.
- **Read the issue through the GitHub API.**: It adds one request for each closed delivery against the hourly budget.
- **Use the raw `state_reason` value.**: A value that GitHub chooses adds a series for each value, which ADR 0009 forbids for sender text.
- **Drop the delivery when no reason is given.**: The item closed, so a dropped delivery understates throughput.
- **The OTLP name of the body, `devops_cli_roadmap_items_closed_total`, in `INSTRUMENTS`.**: `prime_counter` does not create an OTLP instrument, so the zero-at-start requirement and the `/metrics` scrape would not hold.
- **Defer the panel to #3655.**: The row test fails without a panel, and the panel is about ten lines.
