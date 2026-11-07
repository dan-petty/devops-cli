# Tasks

## 1. Show the masked reason of a failed write

Kind: behavior

Reads: `src/devops_cli/roadmap/intake.py`, `src/devops_cli/security/sanitizer.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/roadmap/intake.py`, `tests/roadmap/test_roadmap_intake.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_intake.py`, assert that the failure text names `GitHubOperationError: HTTP 502: Bad Gateway`, add a case with a token in the error text, and keep the case that writes the other candidates
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_intake.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/intake.py`, set `PlacementFailure.error` in `_failed_placement` to the class of the error and its text, masked with `redact_text` and bounded to `CONST_MAX_ERROR_DETAIL_LENGTH`, and give that field to the logger warning
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_intake.py` passes

## Criteria

- Group 1: The failure text SHALL name the class and the masked text of the failed write of each skipped candidate.
- Group 1: The failure text SHALL NOT contain a token from the error text.
- Group 1: Intake SHALL write the other candidates after one write fails.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
