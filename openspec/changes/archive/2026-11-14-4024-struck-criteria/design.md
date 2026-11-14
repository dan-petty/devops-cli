# Design

## Context

`acceptance_criteria` reads each top-level item and removes the task marker with `_TASK_MARK`. A strike through the item leaves the `~~` marks in the text.

## Goals

- Drop a cancelled item.
- Keep an active item that holds an inline strikethrough.

## Decisions

- **The span wraps the text.** The text starts and ends with `~~` only when the span covers the whole item. An inline span leaves other text before or after it.
- **The checked form.** `~~[x] Dropped~~` arrives as `~~Dropped~~` after the task marker is removed, so the same condition drops it.

## Risks

- A criterion that begins and ends with `~~` as literal text is dropped. That text is a strikethrough in Markdown, so the reader treats it as cancelled.

## Tests

- An unchecked struck item and a checked struck item give no criterion.
- A mixed list keeps the active items in order.
- An active item with an inline span keeps its text.
