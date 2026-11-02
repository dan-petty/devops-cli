# Proposal

## Why

A findings.json that fails ReviewSessionPayload validation ends the command with a raw pydantic traceback. No reader reports the file name or the failing field. #2644.

## What Changes

- Add a shared load_session_payload function in review/session.py that catches pydantic.ValidationError and raises the project's ValidationError with the file path and dotted field path.
- Update list_findings, _read_session_file, and _session_findings in commands/review.py to call the shared loader.
- Update read_session in review/handoff.py to call the shared loader.
- Add a test that asserts the loader raises the project's ValidationError with the expected message on an invalid file.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-error-exit`: review-session-file-validation-error

## Impact

- Code: `src/devops_cli/review/session.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/review/handoff.py`
- Tests: `tests/review/test_session_loader.py`

## Feasibility

- The code in src/devops_cli/commands/review.py shows ReviewSessionPayload.model_validate_json called without a try/except in list_findings, _read_session_file, and _session_findings.
- The import from devops_cli.exceptions.validation import ValidationError in commands/review.py confirms the project has its own error type.
- The verify_finding command already catches the project's ValidationError and exits with code 1, showing the pattern to follow.
- The issue's reproduction uses RFC 5737 address 203.0.113.7 and a temporary data directory, so no network or cluster is needed.
- First check: uv run devops ci test tests/review/test_session_loader.py runs the new loader test offline.
- Second check: DEVOPS_CLI_DATA_DIR=<tmp> uv run devops review findings on a session with an invalid findings.json exits non-zero with no traceback.

## Existing Tool Considered

Pydantic, already used for ReviewSessionPayload, provides ValidationError with structured loc tuples. The project already has a review error type in devops_cli.exceptions.validation. No additional library is needed. The written cost is one shared loader function of about 15 lines, four call-site changes, and one test.
