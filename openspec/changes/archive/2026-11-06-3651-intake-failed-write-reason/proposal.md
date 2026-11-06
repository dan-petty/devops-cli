# Proposal

## Why

When a write of `devops roadmap intake` fails, the failure line names only the class of the error, for example `(GitHubOperationError)`. A person cannot see the status code or the message of GitHub without a new run, and each new run spends a model call again (#3651).

## What Changes

- `_failed_placement` in `src/devops_cli/roadmap/intake.py` sets `PlacementFailure.error` to the class of the error and its text, masked with `redact_text` and bounded to `CONST_MAX_ERROR_DETAIL_LENGTH` characters.
- The logger warning and `raise_for_failed_placements` read that one field, so the console and the log show the same masked reason.
- `tests/roadmap/test_roadmap_intake.py` asserts the reason in the failure line, asserts that a token in the error text does not appear, and keeps the test that the other candidates are written.
- The `roadmap-intake-failures` capability is new, because the failure line is output that a person reads.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-intake-failures`: What the failure line of a failed intake write shows

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/intake.py`
- Tests: `tests/roadmap/test_roadmap_intake.py`

## Feasibility

- The premise holds in the code at `origin/main`. `_failed_placement` builds `PlacementFailure(subject.number, subject.title, type(exc).__name__)`, so the field holds only the class. `raise_for_failed_placements` formats that field into the `RoadmapIntakeError` text, which the console prints.
- A run of the existing test `test_confirm_reports_what_it_placed_names_what_it_skipped_and_exits_one` shows the failure line `#<n> (GitHubOperationError)`, with no status code and no message, although the raised error holds `HTTP 502: Bad Gateway`.
- A run with a token in the error text showed that the logger warning holds the masked token, so the log path already masks. The new test therefore guards the console text, which the failure line now carries.
- `redact_text` in `src/devops_cli/security/sanitizer.py` masks a GitHub token as `<masked-github-token>`. `GitHubOperationError` keeps the status code and the GitHub message in its text (`src/devops_cli/exceptions/git.py`).

## Existing Tool Considered

`redact_text` of `src/devops_cli/security/sanitizer.py` masks the text, and the text of `GitHubOperationError` gives the reason. The change adds no tool or library and deletes no code. The written cost is about 2k tokens to build, keep and fix, and 20 minutes.

## Dependencies

None.
