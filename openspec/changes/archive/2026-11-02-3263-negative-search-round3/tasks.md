# Tasks

## 1. A reason is safe to show, and every verification command has a limit

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/stage_form.py`. Changes: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_verification_reason.py` (new), `tests/roadmap/test_roadmap_implement_negative_search.py`.

- [x] 1.1 Write `tests/roadmap/test_roadmap_implement_verification_reason.py` for a command with a control character in the outcome of a step, in `commands_failure` and in the problem of the gate, for the limit of every program, and for the values and the cuts that mutation left unpinned
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_verification_reason.py` fails on the base
- [x] 1.2 Add `shown`, name the command with it in the step and the gate, and move the limit into `read_verification`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_verification_reason.py tests/roadmap/test_roadmap_implement_negative_search.py tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_stage_form.py`

## 2. A refused verification command is a refused tool

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`. Changes: `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_failure.py`.

- [x] 2.1 Write the tests for the class and the action of a refused program, option, shape and length
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py` fails on the base
- [x] 2.2 Build the rule of the classifier from the message of the step and remove the old alternative
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py`

## 3. The paths of a negative search are checked at plan time

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_stage_paths.py`.

- [x] 3.1 Write the tests for `src/ tests/`, a typo, a folder that the plan creates, a glob and `.`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [x] 3.2 Read the paths of a negative search from `read_negative_search` in `_named`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py tests/roadmap/test_roadmap_stage_form.py`

## 4. The log names no word after a bang

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_tool_log.py`. Changes: `src/devops_cli/roadmap/implement_tool_log.py`, `tests/roadmap/test_roadmap_implement_tool_log.py`.

- [x] 4.1 Write the test that a command that starts with `!` is logged as other
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_tool_log.py` fails on the base
- [x] 4.2 Take `!` out of the known programs of the log
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_tool_log.py`

## 5. Archive

Kind: other.

- [x] 5.1 Archive the change
  - Verification: `uv run devops openspec archive 3263-negative-search-round3` and `uv run devops openspec check`

## Workflow follow-up

- #3276 (several names in one negative search) is the issue for the shape. The refused lines of #2610 and the rewrite that passes are in a note for a separate plan fix.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
