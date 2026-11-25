# Proposal: #5319

## Why

`devops tf drift` always exits `0`, ignores OpenTofu `check` blocks, and takes a state lock during `tofu plan -refresh-only` (`src/devops_cli/commands/tf.py`, `src/devops_cli/tf/analysis.py`). A drifted stack, a failed or unknown check, or a failing refresh plan therefore reports success to CI and callers (#5319, part of #5311).

## What Changes

- Run `read_plan_drift` as `tofu plan -refresh-only -detailed-exitcode -lock=false -out=<plan file>` in a temporary directory without `-json`, then read `drifted`, `failed_checks`, and `unknown_checks` from `tofu show -json <plan file>` (`checks[].status` and `address.to_display`).
- Return a typed `PlanDriftResult` model from `read_plan_drift` (empty with `plan_returncode == 0` when uninitialized; early return with `plan_returncode` and `plan_error` without running `tofu show` when `tofu plan` exits outside `0` or `2`).
- Update `IaCDriftReport`, `detect_drift`, and `devops tf drift` (`table` and serialized `--format`) so exit code `1` wins on plan errors or `fail`/`error`/`unknown` checks, exit code `2` is returned on drift (`plan_returncode == 2` or `report.drift_detected`), and exit code `0` is returned only when clean.
- Document exit codes `0`, `1`, and `2` in `devops tf drift --help` and regenerate `docs/commands/tf.md`.

## Capabilities

### New Capabilities

- `tf-drift`: Refresh-only drift exit codes (`0` clean, `1` check failure/unknown or plan error, `2` drift), `-lock=false`, and saved-plan `checks` inspection for `devops tf drift`.

### Modified Capabilities

- None.

## Impact

- `src/devops_cli/models/tf.py`
- `src/devops_cli/tf/analysis.py`
- `src/devops_cli/commands/tf.py`
- `src/devops_cli/lang/en/messages.py`
- `docs/commands/tf.md`
- `tests/tf/test_tf_analysis.py`

## Feasibility

- OpenTofu natively supports `-refresh-only -detailed-exitcode -lock=false -out=<plan>` and `tofu show -json <plan>` exposes top-level `resource_drift` and `checks` (`address.to_display`, `status` in `pass`/`fail`/`error`/`unknown`).
- Confirmed in `src/devops_cli/tf/analysis.py` (`read_plan_drift`, `parse_plan_drift`, `detect_drift`) and `src/devops_cli/commands/tf.py` (`tf_drift`) that `read_plan_drift` currently ignores exit codes and runs without `-lock=false` or `tofu show -json <plan>`.

## Existing Tool Considered

Uses the repository's already-integrated `opentofu/opentofu` binary (`-detailed-exitcode`, `-lock=false`, saved-plan `tofu show -json`), adding only thin Python orchestration and Typer exit-code wiring. Estimated build cost: ~15,000 tokens and ~1 hour.
