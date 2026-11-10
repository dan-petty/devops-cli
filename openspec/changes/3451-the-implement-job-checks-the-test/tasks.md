# Tasks

## 1. Read the test form that a task names

Reads: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/roadmap/implement/implement_test_names.py`, `tests/roadmap/implement/test_roadmap_implement_test_names.py`. Changes: `src/devops_cli/roadmap/implement/implement_test_form.py` (new), `tests/roadmap/implement/test_roadmap_implement_test_form.py` (new).

- [x] 1.1 Add a test in `tests/roadmap/implement/test_roadmap_implement_test_form.py` that a task naming six statuses gives the path and the count six
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_test_form.py` fails on the base
- [x] 1.2 Create `src/devops_cli/roadmap/implement/implement_test_form.py` with `TestForm`, `named_forms(text, paths)` and `collected_items(output)`. `named_forms` gives one form for each path that `is_test_file` accepts when the task text holds the word `parametrized`, reads the count after `parametrized test over` as a digit or a number word from one to twenty, and gives a form with no count when the task states none. A task with no `parametrized` word gives no form. `collected_items` counts the lines of the quiet collection output that hold `::`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_test_form.py` passes

## 2. Refuse a test that does not match its task form

Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_test_form.py`, `src/devops_cli/roadmap/implement/implement_trace.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/lang/en/messages.py`, `tests/support/implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_step_format.py`, `tests/roadmap/implement/test_roadmap_implement_step_trace.py`. Changes: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_step_test_form.py` (new).

- [ ] 2.1 Add a test in `tests/roadmap/implement/test_roadmap_implement_step_test_form.py` that a test which collects eleven items for six named cases stops the group with both counts
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_test_form.py` fails on the base
- [ ] 2.2 Add `_test_form_failure(source, inputs, trace)` to `src/devops_cli/roadmap/implement/implement_step.py` and call it from `_exit_failure` after the verification commands and before the base replay. It returns None for a fix step and for a group whose tasks name no parametrized test. For each form it runs `uv run pytest --collect-only -q` on the named test file through `run_subprocess` under `roadmap.implement.command_timeout_seconds`, records a `check` event with `ImplementTrace.check` that names the file and both counts, and returns a `_Failure` with the class `FailureClass.TEST` and the named test file as its repair path when the count differs, when the collection reports one item for a named parametrized test, or when the collection exits non-zero. A timeout returns the class `FailureClass.TIMEOUT`. Add `BIN_PYTEST` to `src/devops_cli/config/commands.py` and the mismatch text to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_test_form.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
