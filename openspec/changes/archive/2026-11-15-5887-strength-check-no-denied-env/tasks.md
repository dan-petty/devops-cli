# Tasks

## 1. The mutation run takes its test selection from the mutmut table

Kind: behavior. Reads: `.venv/lib/python3.14/site-packages/mutmut/configuration.py`, `.venv/lib/python3.14/site-packages/mutmut/runners/harness.py`, `src/devops_cli/core/process.py`. Changes: `src/devops_cli/roadmap/implement/implement_strength.py`, `pyproject.toml`, `uv.lock`, `tests/roadmap/implement/test_roadmap_implement_strength.py`.

- [x] 1.1 In `tests/roadmap/implement/test_roadmap_implement_strength.py`, add a test that gives the recorded environment of `mutmut run` to the real `build_subprocess_env`, add a test that reads `pytest_add_cli_args_test_selection` of `[tool.mutmut]` during the run and the bytes of `pyproject.toml` after it, and make the timeout test check the selection and that no `pyproject.toml` stays
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/implement/implement_strength.py`, add `_mutmut_test_selection`, which adds the scoped test modules to the table with tomlkit and writes the original bytes back, run `mutmut run` in it with no environment key, and add `tomlkit==0.15.2` to `pyproject.toml` and `uv.lock`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py`

## 2. A command that the process runner refuses stops as a refused tool

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stop_clear.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/failure.py`, `tests/roadmap/implement/test_roadmap_implement_job_scoped.py`.

- [x] 2.1 In `tests/roadmap/implement/test_roadmap_implement_job_scoped.py`, add a test whose pre-push check raises `SecurityError`, and that the stop has the class `refused_tool`, the action left `wait` and the kept work
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_scoped.py` fails on the base
- [x] 2.2 In `_failure_class_of` of `src/devops_cli/roadmap/implement/implement_run.py`, give `refused_tool` for a `SecurityError`, and name this typed source in the docstring of `src/devops_cli/roadmap/failure.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_scoped.py`

## 3. Documents

Kind: other. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`.

- [x] 3.1 Replace `PYTEST_ADDOPTS` with the mutmut table in the text of the strength check, add the refused command to the row `refused_tool`, and add tomlkit to the package manual
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #5891: `ProcessFake` records the environment of a call and does not run the check of `build_subprocess_env`, so a test with `process_fake` does not see a refused key.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
