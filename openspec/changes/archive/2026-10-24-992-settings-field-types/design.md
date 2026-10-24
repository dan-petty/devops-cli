# Design

## Context

Settings values can enter the system through environment variables, configuration files, and CLI commands.
Previously, settings models did not validate assignment.
`_coerce_setting_value` performed manual type casting for some types and ignored others.
Strings with invalid schemes or negative timeouts entered configuration state without validation.

## Goals / Non-Goals

**Goals:**

- Validate every setting value against its declared type and field constraints at load time and during assignment.
- Prevent non-positive, infinite, or NaN values in timeout and duration fields.
- Preserve exact user string inputs for valid URLs while rejecting malformed or ambiguous URLs.
- Prevent sensitive values from appearing in validation errors.
- Ensure commands fail early with exit code 1 when given invalid setting values.

**Non-Goals:**

- Do not alter Valkey URLs (`valkey://`, `valkeys://`) in this change.
- Do not migrate invalid values in existing `config.yaml` files automatically.
- Do not introduce backward-compatibility shims for invalid URL or boolean spellings.

## Decisions

- **Use Pydantic `validate_assignment=True` on all section models.** Every value assigned to a model field triggers validation against its type and constraints.
  - *Rejected Alternative:* Coerce types manually inside `_coerce_setting_value`. Evidence: Manual coercion duplicates Pydantic logic and failed to validate floats, URLs, or negative numbers.
- **Use `hide_input_in_errors=True` on `Settings` and section models.** This prevents secret tokens or credentials embedded in invalid URLs from appearing in error messages.
  - *Rejected Alternative:* Sanitize error strings after validation. Evidence: String sanitization is fragile and can miss credentials formatted in unexpected ways.
- **Combine `TypeAdapter(AnyHttpUrl)` and `httpx2.URL` origin check for HTTP URLs.** This ensures the URL is valid in Pydantic and that httpx2 routes it to the expected host and port.
  - *Rejected Alternative:* Use bare `AnyHttpUrl`. Evidence: `AnyHttpUrl` serializes to an object rather than a string, breaking string operations like `.rstrip("/")` across callers. It also appends trailing slashes.
  - *Rejected Alternative:* Use `httpx2.URL` alone. Evidence: `httpx2.URL` accepts non-standard hosts such as `http://` or port `99999`.
- **Detect list annotations using `typing.get_origin`.** `dotted_set` inspects the field annotation to determine if a comma split is needed.
  - *Rejected Alternative:* Check if the field name ends with `'s'`. Evidence: Field names like `public_ip_bypass` end with `'s'` but are not lists, causing data corruption.

## Risks / Trade-offs

- [Workstations with malformed URLs or invalid numbers in `config.yaml` fail to load] → Callers must update `config.yaml` with valid values as documented in the release notes.
