# Design

## Decisions

- **Redact the source text before the diff.**: Every diff line comes from redacted text, so no post-processing can miss a value.
- **Use `***REDACTED***` as the placeholder.**: It is the placeholder that #2645 uses in file copies.
- **Use `round_trip.edit` to set the credential to the placeholder.**: It edits the YAML value in place and keeps comments and other lines.
- **Keep non-credential values in the diff.**: The preview must still show what the removal changes.
- **Leave the live run path unchanged.**: The live run already redacts copies and prints no value.

## Rejected alternatives

- **Post-process each diff line.**: A value can span lines or contain the key name. Parsing YAML diff lines is fragile.
- **Suppress the diff for credential keys.**: The preview must show the key, file and line. The issue requires a placeholder.
- **Redact every value in the diff.**: The issue requires non-credential values such as `ai.model: llama3` to show.
