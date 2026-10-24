# Proposal

## Why

Issue #992 reports that numeric settings set through environment variables load as raw strings and omit range checks.
`_coerce_setting_value` passes float settings through unchanged.
Values such as `"30"` load as strings without error, and invalid values fail far from configuration loading.
In addition, boolean, URL, and list settings bypass field types during load and assignment.
A field type must be the single validation point for every setting value.

## What Changes

- Add field constraints `gt=0` and `allow_inf_nan=False` to timeout, duration, and interval fields.
- Configure `validate_assignment=True` and `hide_input_in_errors=True` on every section model.
- Configure `hide_input_in_errors=True` on `Settings`.
- Add an HTTP URL alias type that validates URL structure with Pydantic and checks origin equality with httpx2.
- Add a service URL alias type for cluster services that validates `k8s://` URLs with `parse_service_url`.
- Update `parse_service_url` error messages to omit user values and report reasons alone.
- Update `dotted_set` to detect list fields from type annotations rather than key suffixes.
- Remove manual type coercion from `_coerce_setting_value` and delete `_typed_placeholder`.
- Format validation errors on a single line naming the full dotted key and reason.
- Ensure `devops config set` and `devops ai config` exit 1 on invalid values and leave configuration unchanged.
- This change alters observable behavior when loading or setting invalid settings values.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: `devops config set` and settings loading validate field types and reject invalid inputs.

## Impact

- `src/devops_cli/config/settings.py`: Model configurations, field constraints, URL aliases, error formatting, and `dotted_set` updates.
- `src/devops_cli/k8s/service_proxy.py`: `parse_service_url` error messages state reasons without embedding URLs.
- `src/devops_cli/commands/config.py`: Single-line error display and exit 1 on refused settings.
- `src/devops_cli/commands/ai.py`: Handle invalid configuration assignment with exit 1.
- `src/devops_cli/commands/k8s/networking.py`: Avoid in-place mutation of list settings.
- `src/devops_cli/telemetry/tracer.py`: Telemetry fallback stays disabled when telemetry variables fail validation.

## Feasibility

- Confirmed with Pydantic 2.13.5 and httpx2 2.13.0 on Python 3.14.7.
- Verified that `TypeAdapter(AnyHttpUrl)` validates URL syntax, port limits, and IDN hostnames.
- Verified that `httpx2.URL(v).origin == httpx2.URL(str(parsed)).origin` detects host parsing divergences.
- Verified that Pydantic `validate_assignment=True` validates booleans, numbers, paths, and URLs during assignment.
- Verified that Pydantic `hide_input_in_errors=True` excludes sensitive input values from error records.
- Verified that `_is_list_annotation` correctly identifies `list[str]` and `list[str] | None`.

## Existing Tool Considered

Pydantic and httpx2 cover URL parsing, type validation, and assignment validation directly.
The standard library `typing` module handles type annotation inspection.
This change deletes `_typed_placeholder` and manual type coercion logic in `_coerce_setting_value`.
No new third-party dependency is required.
