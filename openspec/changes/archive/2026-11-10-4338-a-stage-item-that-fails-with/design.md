# Design

## Decisions

- **Use `AIClientError.reason` and `body_error_text`.**: Both exist, and `body_error_text` already hides the quoted text of a provider error, so the reply of the model cannot reach the report.
- **Log in `_failure_of`.**: Every plan failure passes through it, so one line per failed item needs one place.
- **Do not change `StructuredOutputValidationError`.**: Its failure text already names the violations and holds no reply.

## Rejected alternatives

- **Print `str(exc)` as it is.**: The message of some provider errors quotes the reply of the model, and the report goes to GitHub.
