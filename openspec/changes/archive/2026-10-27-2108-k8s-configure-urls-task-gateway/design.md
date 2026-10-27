# Design

## Context

See `proposal.md` for motivation.
`devops k8s configure-urls` discovers cluster services and collects updated settings in the `configured` dictionary.
If `configured` contains entries, the command calls `save_settings` and outputs the table.
The helper `_update_task_gateway_urls` does not receive `configured` and does not add updated keys to it.

## Goals / Non-Goals

**Goals:**
- Pass `configured` to `_update_task_gateway_urls`.
- Record each updated task gateway URL key in `configured`.
- Save configuration settings when only task gateway URLs change.
- Output updated task gateway URL keys in the service targets table.

**Non-Goals:**
- Modify task gateway URL selection logic or conditions.
- Modify how `save_settings` performs round-trip serialization.

## Decisions

### Update task gateway URLs helper signature and mapping

Pass `configured: dict[str, str]` to `_update_task_gateway_urls(settings, configured, full_gw)`.
When `_should_update_url` returns true for a task, set the URL and insert `ai.tasks.<task>.api_base_url` into `configured`.

- **Rejected alternative: Call save_settings unconditionally without checking configured.**
  Evidence: `configure-urls` must not write files or audit records when no URL changes.
- **Rejected alternative: Detect settings changes by deep comparison of settings models.**
  Evidence: The command already uses `configured` to report updated URLs to the user in `format_k8s_service_targets_table`. Keeping them aligned prevents inconsistencies between reports and file writes.

## Risks / Trade-offs

- [Task gateway URLs appear in the configured services table] → This output accurately reflects the changes that the command made to the configuration.
