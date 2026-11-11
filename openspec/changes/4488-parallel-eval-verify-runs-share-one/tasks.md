# Tasks

## 1. Add the unique store file helper

Reads: `src/devops_cli/roadmap/implement/implement_eval_run.py`, `tests/core/test_core_repo.py`. Changes: `src/devops_cli/core/repo.py`, `tests/core/test_core_repo.py`.

- [x] 1.1 `test_two_store_files_of_one_second_are_two_files` in `tests/core/test_core_repo.py` fails first
  - Verification: `$ uv run devops ci test tests/core/test_core_repo.py` fails on the base
- [x] 1.2 Add `create_store_file(folder, suffix=".json")` to `src/devops_cli/core/repo.py`: resolve the store folder with `resolve_store_path`, create it with `mkdir(parents=True, exist_ok=True)`, take the stamp `%Y%m%dT%H%M%SZ` from `datetime.now(UTC)`, call `tempfile.mkstemp(prefix=f"{stamp}-", suffix=suffix, dir=store)`, close the descriptor and return the path. The test freezes the clock with time-machine, uses the `isolate_data_dir` fixture, calls the helper twice in a store folder that is absent, and asserts two different paths with both files present
  - Verification: `$ uv run devops ci test tests/core/test_core_repo.py` passes

## 2. Give the verify command its own report file

Reads: `src/devops_cli/core/repo.py`, `src/devops_cli/commands/roadmap_eval_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`. Changes: `src/devops_cli/commands/roadmap_eval_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`.

- [x] 2.1 `test_two_runs_that_start_in_one_second_keep_their_cases_in_two_reports` in `tests/roadmap/stage/test_roadmap_stage_verify_eval.py` fails first: with the clock frozen, the first run starts a second run on its own thread inside its model call, and the test expects two reports, each with the cases of its run
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` fails on the base
- [x] 2.2 In `src/devops_cli/commands/roadmap_eval_verify.py`, import `create_store_file` in place of `resolve_store_path`, and replace the stamp line with `target = resume or create_store_file(_STORE)`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` passes

## 3. State the unique report file in the workflow page

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 In the stopped-run bullet of `docs/ROADMAP_WORKFLOW.md`, state that each run creates its own report file, so two runs that start in the same second get two files
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py` passes
