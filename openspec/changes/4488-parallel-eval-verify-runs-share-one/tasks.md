# Tasks

## 1. Add the unique store file helper

Reads: `src/devops_cli/roadmap/implement/implement_eval_run.py`, `tests/core/test_core_repo.py`. Changes: `src/devops_cli/core/repo.py`, `tests/core/test_core_repo.py`.

- [ ] 1.1 `test_create_store_file_gives_two_files_in_one_second` in `tests/core/test_core_repo.py` fails first
  - Verification: `$ uv run devops ci test tests/core/test_core_repo.py` fails on the base
- [ ] 1.2 Add `create_store_file(directory, moment=None)` to `src/devops_cli/core/repo.py`: resolve the store folder with `resolve_store_path`, create it with `mkdir(parents=True, exist_ok=True)`, take the stamp `%Y%m%dT%H%M%SZ` from `moment or datetime.now(UTC)`, call `tempfile.mkstemp(prefix=f"{stamp}-", suffix=".json", dir=store)`, close the descriptor and return the path. The test sets `DEVOPS_CLI_DATA_DIR` to a `tmp_path` folder, calls the helper twice with one moment, and asserts two different paths with both files present, and once with a store folder that is absent
  - Verification: `$ uv run devops ci test tests/core/test_core_repo.py` passes

## 2. Give the verify command its own report file

Reads: `src/devops_cli/core/repo.py`, `src/devops_cli/commands/roadmap_eval_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`. Changes: `src/devops_cli/commands/roadmap_eval_verify.py`, `tests/commands/test_roadmap_eval_verify_store.py` (new).

- [ ] 2.1 `test_the_report_target_gives_two_files_in_one_second` in `tests/commands/test_roadmap_eval_verify_store.py` fails first
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_eval_verify_store.py` fails on the base
- [ ] 2.2 In `src/devops_cli/commands/roadmap_eval_verify.py`, import `create_store_file` from `devops_cli.core.repo`, add `_report_target(resume, moment=None)` that returns the resume path or `create_store_file(_STORE, moment)`, and replace the stamp line with `target = _report_target(resume)`. Drop the now unused `resolve_store_path` import. The new test sets `DEVOPS_CLI_DATA_DIR` to a `tmp_path` folder, calls `_report_target` twice with one moment and asserts two different `.json` files under `roadmap_eval/verify`, and calls it with a resume path and asserts that path and no new file
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_eval_verify_store.py` passes

## 3. State the unique report file in the workflow page

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 3.1 Add one sentence to the stopped-run bullet of `docs/ROADMAP_WORKFLOW.md` that says each run without `--resume` creates its own report file in the verify store folder, also when two runs start in the same second, and that `--resume` keeps writing the file it names
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py` passes
- [ ] 3.2 Edit `docs/ROADMAP_WORKFLOW.md` to state that each run without `--resume` creates its own report file
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
