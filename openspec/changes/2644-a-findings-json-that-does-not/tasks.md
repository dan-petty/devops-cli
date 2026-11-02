# Tasks

## 1. Add shared session payload loader

Reads: none. Changes: `src/devops_cli/review/session.py`, `tests/review/test_session_loader.py` (new).

- [ ] 1.1 Write a test that creates a temporary findings.json with a missing required field, calls load_session_payload, and asserts it raises the project's ValidationError with the file path and field path in the message, and verify that `uv run devops ci test tests/review/test_session_loader.py` fails on the base
- [ ] 1.2 Add a load_session_payload function to src/devops_cli/review/session.py. It takes a Path, reads the file text, calls ReviewSessionPayload.model_validate_json, catches pydantic.ValidationError (imported as PydanticValidationError to avoid name collision), and raises the project's ValidationError from devops_cli.exceptions.validation with a message that includes the file path and each error's loc joined by dots. Write a test in tests/review/test_session_loader.py that creates a temporary findings.json with a missing required field, calls load_session_payload, and asserts it raises the project's ValidationError with the file path and field path in the message, and verify that `uv run devops ci test tests/review/test_session_loader.py` passes

## 2. Route all four readers through the shared loader

Reads: none. Changes: `src/devops_cli/commands/review.py`, `src/devops_cli/review/handoff.py`.

- [ ] 2.1 In src/devops_cli/commands/review.py, replace the three direct calls to ReviewSessionPayload.model_validate_json in list_findings, _read_session_file, and _session_findings with calls to load_session_payload imported from devops_cli.review.session. In src/devops_cli/review/handoff.py, replace the direct call in read_session with load_session_payload. Remove the now-unused direct import of ReviewSessionPayload from the call sites if it is no longer needed there, and verify that `uv run devops ci test tests/review/test_session_loader.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
