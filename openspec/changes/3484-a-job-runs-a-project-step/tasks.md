# Tasks

## 1. Run a project step only where the target declares it

Reads: `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_hooks.py`, `src/devops_cli/roadmap/implement_pull.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement_steps.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `.devops/roadmap.toml`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_project_steps.py`.

- [x] 1.1 Add `tests/roadmap/test_roadmap_implement_project_steps.py`: a target with no declaration skips the docs step in `_finish_change` and in `_scoped_rounds`, and skips the archive step, and ends with a ready pull request; an agent edit of the declaration changes no step; a target that declares the steps runs them; the comment names each skipped step; a declaration that is not valid stops the item
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_project_steps.py` fails on the base
- [x] 1.2 Add `implement_steps.py` (`ProjectStep`, `declared_steps`), the gate `_runs` in `implement_run.py`, the line of a skipped step in the comment, `ChangeFacts.archive_required`, and `.devops/roadmap.toml` for devops-cli. The test worlds declare both steps on `main`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_project_steps.py tests/roadmap/test_roadmap_implement_job.py tests/roadmap/test_roadmap_implement_job_scoped.py` passes

## 2. Do not retry a stop on a read-only path

Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/stop_clear.py`. Changes: `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_implement_project_steps.py`.

- [x] 2.1 Add cases: the text of the stop of the issue has the class `read_only_path`, the table lists the class with the action `wait`, and a new runner image does not clear the stop
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_implement_project_steps.py` fails on the base
- [x] 2.2 Add the class `read_only_path` with the action `wait` and its rule to `failure.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_implement_project_steps.py` passes

## 3. State the rule in the documents

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`.

- [x] 3.1 State the declaration file, the read from the default branch, the skipped-step line and the class `read_only_path` in both documents. Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Pending a person: a live run of a dotfiles item to a pull request (#3511).
