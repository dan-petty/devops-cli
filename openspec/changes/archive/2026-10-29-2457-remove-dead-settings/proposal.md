# Proposal

## Why

`cloudflare.access.enabled` and `cloudflare.access.idp` hold a value that no code reads (#2457).

`devops cloudflare access` reads only `allowed_emails`, `bypass_ips` and `public_ip_bypass`; no code takes `enabled` or `idp`.
A person who sets one of them sees no effect. A dead setting is a cost of tokens to keep and fix, and it misleads a person into setting a value that does nothing.

## What Changes

- Remove `enabled` and `idp` from `CloudflareAccessConfig` in `src/devops_cli/config/settings.py`.
- Remove `enabled: false` and `idp: google` from the `access` section of `config.example.yaml`.
- Regenerate the documentation, which drops the `enabled` and `idp` entries of the `access` row in `docs/CONFIGURATION.md`.
- A config file that still holds a removed key still loads, because the `access` section drops a key it does not declare.
- Keep `telemetry.logfire`: the issue's premise that no code reads it is incomplete. `_init_logfire_if_enabled` reads it as the ambient fallback for the `--logfire` flag on the review commands, and a test covers it. Removing it would change that behavior, so the change removes it not.
- `config show` and `config env` list none of the two, so no command output, manifest or service behavior changes.
- This change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/config/settings.py`.
- Tests: `tests/config/test_removed_settings_fields.py`.
- Documents: `config.example.yaml`, `docs/CONFIGURATION.md`, `README.md`.

## Feasibility

- Verified against the source that `CloudflareAccessConfig` (line 431) declares `enabled` and `idp`, and that `devops cloudflare access` (src/devops_cli/commands/cloudflare.py) reads only `allowed_emails`, `bypass_ips` and `public_ip_bypass`, and no code reads `enabled` or `idp`.
- Verified that the issue's premise is incomplete for `telemetry.logfire`: `src/devops_cli/commands/review.py` line 175 reads `getattr(settings.telemetry, "logfire", False)` as the fallback for the `--logfire` flag when it is not given, and `tests/test_telemetry_logfire.py` covers that read. The issue's `git grep` searched the dotted name and missed the `getattr` form.
- Verified that `config.example.yaml` holds `enabled: false` and `idp: google` under `access` and holds no `telemetry.logfire` line.
- Verified that `devops config show` and `devops config env` list none of the two, since neither carries a `Variable` marker.
- Verified that the `access` section drops a key it does not declare, so a file that still holds a removed key loads.
- Verified that the two removed fields stay off the model and `telemetry.logfire` stays on it after `devops docs generate --sync-readme`, and that `devops docs check` passes.

## Existing Tool Considered

The Pydantic settings models and `devops docs generate` already provide the setting declaration and its documentation. Removing two dead fields needs no new tool or library; the cost of keeping them is the tokens to keep and fix two values no reader takes.
