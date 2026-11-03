# Tasks

## 1. A refused command keeps its class, and the output is safe to show

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_implement_verification_reason.py`.

- [x] 1.1 Write the tests for the class of a refused command with the words of another rule, and for the output of a failed command and of a matched search with control characters
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_implement_verification_reason.py` fails on the base
- [x] 1.2 Read the rule for a refused command first and anchored, and escape each line of the output in `_tail`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_implement_verification_reason.py tests/roadmap/test_roadmap_implement_step.py`

## 2. A path and a word that cannot work are refused

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/implement_shell_policy.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py`, `tests/roadmap/test_roadmap_implement_verification_reason.py`.

- [x] 2.1 Write the tests for a trailing slash on a file, for a NUL byte and a lone surrogate in a word, for the backtick message, and for the fallback to the words of a refused or unreadable command
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py tests/roadmap/test_roadmap_implement_verification_reason.py` fails on the base
- [x] 2.2 Add `has_folder` and the check of a trailing slash, and refuse a word that is no argument in `read_verification`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py tests/roadmap/test_roadmap_implement_verification_reason.py tests/roadmap/test_roadmap_stage_form.py`

## 3. Names and wrapping

Kind: other. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/stage_form.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 3.1 Rename the limit to `CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS` and fix its note, wrap the two docstrings, and rename the two local names that hid `shown`
  - Verification: `! git grep -n CONST_ROADMAP_IMPLEMENT_SEARCH_CHARS -- src tests` and `uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py`

## 4. Archive

Kind: other.

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 3263-negative-search-round4` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
