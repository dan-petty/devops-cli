# Tasks

## 1. The step runs a negative search in a fixed shape

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/stage_form.py`, `tests/support/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_negative_search.py` (new), `tests/roadmap/test_roadmap_implement_shell_policy.py`.

- [x] 1.1 Write `tests/roadmap/test_roadmap_implement_negative_search.py` and the policy tests for the scenarios of "A negative search is a verification command in a fixed shape"
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_negative_search.py` fails on the base
- [x] 1.2 Add `read_negative_search` and `verification_problem` to `implement_shell_policy.py`, and run the negative search in `commands_failure` with `--` before the paths and a pass on exit 1
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_negative_search.py tests/roadmap/test_roadmap_implement_shell_policy.py tests/roadmap/test_roadmap_implement_step.py`

## 2. The gate reads the table of the step

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_shell_policy.py`. Changes: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_form.py`.

- [x] 2.1 Write the tests for the scenarios of "A verify command has the project form" that give the reason of the step
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [x] 2.2 Replace `_valid_verify` with `_verify_problem`, which asks `verification_problem`, add the problem text, and give the options and the signs in the stage prompt
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py tests/roadmap/test_roadmap_implement_negative_search.py tests/roadmap/test_roadmap_stage_prompt_rules.py tests/roadmap/test_roadmap_stage_kind.py`

## 3. Documents

Kind: other. Reads: `docs/TESTING.md`. Changes: `docs/TESTING.md`.

- [x] 3.1 Describe the fixed shape of the negative search in `docs/TESTING.md`
  - Verification: `uv run devops ci docs`

## 4. Archive

Kind: other.

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 3263-negative-search-verify` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
