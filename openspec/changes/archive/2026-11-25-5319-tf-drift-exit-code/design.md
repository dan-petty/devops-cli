# Design

## Decisions

- **Run `tofu plan -refresh-only -detailed-exitcode -lock=false -out=<plan>` in a temporary directory**: Saving the binary plan into a `tempfile.TemporaryDirectory()` keeps the stack directory clean, avoids state locks during read-only drift checks, and gives `tofu show -json <plan>` both `resource_drift` and top-level `checks`.
- **Introduce `PlanDriftResult` and extend `IaCDriftReport`**: `read_plan_drift` returns `PlanDriftResult` (`drifted`, `failed_checks`, `unknown_checks`, `plan_returncode`, `plan_error`) matching `TFLintResult`/`TFOutputResult`, and `IaCDriftReport` exposes `failed_checks`, `unknown_checks`, and `plan_error` (defaulted empty) so serialized JSON/YAML output preserves full diagnostics alongside exit codes.
- **Exit code precedence (`1 > 2 > 0`)**: Any `plan_returncode not in (0, 2)` aborts before `tofu show` and exits `1` with `plan_error`. Any `failed_checks` (`fail`/`error`) or `unknown_checks` (`unknown`) prints check addresses and exits `1`, overriding drift (`2`) because check failures invalidate confidence in the plan. Any drift (`plan_returncode == 2` or `report.drift_detected`) emits output first and exits `2`. Uninitialized directories keep exiting `0` with the existing state-unavailable warning.

## Rejected alternatives

- **Parse `tofu plan -refresh-only -json` streaming UI events**: Rejected because the streaming UI output does not include the top-level `checks` array from saved plans and misses exit-code semantics when paired with `-detailed-exitcode`.
- **Add `--lock`/`--no-lock` flags to `devops tf drift`**: Rejected because drift detection is strictly read-only and should never acquire the state lock.
