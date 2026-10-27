# Proposal

## Why

Issue #2108 reports that `devops k8s configure-urls` does not save task gateway URLs.
The command saves settings only when its configured table contains an entry.
`_update_task_gateway_urls` modifies task gateway URLs in memory but does not add them to the table.
When only task gateway URLs change, the command saves nothing.

## What Changes

- Modify `_update_task_gateway_urls` to record updated task gateway URLs in the configured mapping.
- Update `devops k8s configure-urls` to save settings and report updated task gateway URLs when only task gateway URLs change.
- Add an automated test that verifies `devops k8s configure-urls` saves task gateway URLs to the configuration file.

This change fits into one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: Update `devops k8s configure-urls` scenarios to verify that updating task gateway URLs saves the configuration and reports the changed keys.

## Impact

- Modified file: `src/devops_cli/commands/k8s/networking.py`.
- Modified tests: `tests/test_k8s_networking.py`.
- No breaking changes or public API removals occur.

## Feasibility

The premise was verified directly against the source code of `src/devops_cli/commands/k8s/networking.py`.
Line 834 calls `_update_task_gateway_urls(settings, full_gw)`.
The function does not accept the `configured` dictionary and does not insert updated keys into it.
Line 981 tests `if configured:` before calling `save_settings(settings)`.
When other service URLs do not change, `configured` stays empty and `save_settings` does not execute.
The issue was documented during pull request #1999 in `openspec/changes/archive/2026-10-24-1999-config-round-trip/design.md`.

## Existing Tool Considered

This defect exists in internal CLI routing logic for Kubernetes service discovery.
No third-party tool or open library configures internal application settings for this command.
Implementing this fix in internal code costs approximately 5 lines of code, 10,000 tokens to build and verify, and 15 minutes of elapsed time.
No internal code is deleted.
