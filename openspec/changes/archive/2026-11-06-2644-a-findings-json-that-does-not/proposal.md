# Proposal

## Why

A findings.json that fails ReviewSessionPayload validation ends the command with a raw pydantic traceback. No reader reports the file name or the failing field. #2644.

## What Changes

- Add a shared load_session_payload function in review/session.py that catches pydantic.ValidationError and raises the project's ValidationError with the file path and dotted field path.
- Update list_findings, _read_session_file, and _session_findings in commands/review.py to call the shared loader.
- Update read_session in review/handoff.py to call the shared loader.
- Add a loader test and a CLI test that runs each of the four readers on an invalid file.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-error-exit`: a command reports a review session file that does not validate in one error line

## Impact

- Code: `src/devops_cli/review/session.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/review/handoff.py`
- Tests added: `tests/review/test_session_loader.py`, `tests/commands/test_review_invalid_session_file.py`
- Tests that must keep passing:
  - `tests/commands/test_review_adjudication.py`: `test_verdicts_given_at_once_on_one_session_all_land` patches `devops_cli.commands.review._read_session_file` (line 339), so the function keeps its name and its `(session_dir, file_name)` arguments.
  - `tests/commands/test_review.py` and `tests/review/test_review_intake_handoff.py` drive `review verify` and `review intake` on valid files.
- Callers that keep working: `ai/review/runner.py` line 1272 calls `handoff.read_session` on the file that the review has just written.

## Feasibility

The premise holds on origin/main (`d5dc9211`). This branch adds only files under `openspec/changes/`, so its `src/` is the same. The issue reproduction, run with a temporary data directory and no network request (`DEVOPS_CLI_DATA_DIR=<tmp> uv run devops review findings`), exits 1 and prints a Rich traceback. Its last lines are:

```
│ ❱ 1122 │   payload = ReviewSessionPayload.model_validate_json(source.read_text(encoding="utf-8"))
ValidationError: 1 validation error for ReviewSessionPayload
network_references.0.reputation.outcome
  Field required [type=missing, input_value={'target': '203.0.113.7',...ation_summary': 'Clean'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
```

- `git grep -n 'ReviewSessionPayload.model_validate_json' src/` lists exactly four call sites outside the schema: `commands/review.py` lines 1122, 1163 and 2066, and `review/handoff.py` line 112. Each has no handler.
- The four readers map to four commands: `review findings` (line 1122), `review verify` and the other verdict commands (`_read_session_file`, line 1163), `review corpus score` (`_session_findings`, line 2066) and `review intake` (`read_session`, line 112).
- The exit seam already does the reporting. `OTelTyper` in `src/devops_cli/core/cli.py` prints a `DevOpsCLIError` as one error line and exits with its `exit_code`. The `command-error-exit` spec says that no command module reports such an error itself. So the loader only raises the project's `ValidationError`, and no command module adds a catch.
- `review verify` does not show a traceback today. Pydantic's `ValidationError` is a `ValueError`, so `verify_finding` catches it and prints a four-line "Cannot update finding: verdict invariants violated" message with no file path. The loader fixes this too, because the project's `ValidationError` matches the earlier `except ValidationError` in that command.
- A prototype of the loader and the four call-site changes, kept out of this pull request, made the two planned test files pass (6 tests), and the 77 tests of `tests/commands/test_review.py`, `tests/commands/test_review_adjudication.py`, `tests/commands/test_review_dry_run.py` and `tests/review/test_review_intake_handoff.py` pass with it.

## Existing Tool Considered

Pydantic, already used for ReviewSessionPayload, provides ValidationError with structured loc tuples. The project already has a review error type in devops_cli.exceptions.validation. No additional library is needed. The written cost is one shared loader function of about 15 lines, four call-site changes, and two test files.
