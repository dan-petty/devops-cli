# Design

## Context

See `proposal.md` - Why.
`cloudflare.access.enabled` and `cloudflare.access.idp` hold a value no reader takes: the Cloudflare reader takes only `allowed_emails`, `bypass_ips` and `public_ip_bypass`.
`telemetry.logfire` holds a value that a reader does take: `_init_logfire_if_enabled` reads it as the ambient fallback for the `--logfire` flag on the review commands.

## Goals / Non-Goals

**Goals:**
- Remove `enabled` and `idp` from `CloudflareAccessConfig`.
- Remove `enabled: false` and `idp: google` from the `access` section of `config.example.yaml`.
- Regenerate the documentation so the `enabled` and `idp` entries of the `access` row are gone.
- Keep a config file that still holds a removed key able to load.

**Non-Goals:**
- Remove `telemetry.logfire`, which has a reader and a test.
- Change the Cloudflare reader, which already takes `allowed_emails`, `bypass_ips` and `public_ip_bypass`.
- Add a shim or a backward-compatibility path for the removed keys.

## Decisions

### Decision 1: Remove `enabled` and `idp` and keep the section dropping an unknown key

`enabled` and `idp` are deleted from `CloudflareAccessConfig`.
The section drops a key it does not declare, so a config file that still holds a removed key loads and the value is dropped rather than kept.

*Alternatives considered:*
- Keeping the fields and marking them deprecated: rejected because alpha software keeps no backward compatibility, so a change removes the old path and adds no shim.
- Adding an explicit `extra="forbid"` to the section: rejected because it would turn a file that loads today into one that refuses to load, a change in behavior the issue does not ask for.

### Decision 2: Keep `telemetry.logfire` because it has a reader and a test

The issue's premise that no code reads `telemetry.logfire` is incomplete: `src/devops_cli/commands/review.py` line 175 reads `getattr(settings.telemetry, "logfire", False)` as the fallback for the `--logfire` flag when it is not given, and `tests/test_telemetry_logfire.py` covers that read.
The acceptance criteria accept a field that is deleted or has a reader a test covers; `telemetry.logfire` has the reader, so it stays.

*Alternatives considered:*
- Deleting `telemetry.logfire` too: rejected because it would change the ambient behavior of `devops review path`, `branch` and `pr` and break `tests/test_telemetry_logfire.py`, a change in behavior the issue does not ask for.

### Decision 3: Regenerate the documentation instead of editing it by hand

`devops docs generate --sync-readme` rebuilds `docs/CONFIGURATION.md` from the models, so the `enabled` and `idp` entries of the `access` row drop on their own, and the `logfire` row stays.

*Alternatives considered:*
- Editing `docs/CONFIGURATION.md` by hand: rejected because `devops docs check` would then flag the file as out of date.

### Decision 4: Carry no spec delta

`config show` and `config env` list none of the two, so no command output, manifest or service behavior changes.
The change sets `skip_specs: true` in `.openspec.yaml`.

*Alternatives considered:*
- Writing a spec delta: rejected because the change alters no behavior a consumer observes.
