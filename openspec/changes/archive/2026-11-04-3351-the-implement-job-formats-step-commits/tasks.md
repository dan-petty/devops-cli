# Tasks

## 1. Build the step commit title from the item title

Reads: `CONTRIBUTING.md`, `src/devops_cli/roadmap/commit_title.py`, `src/devops_cli/roadmap/pull_form.py`. Changes: `src/devops_cli/roadmap/step_commit.py` (new), `tests/roadmap/test_step_commit_title.py` (new).

- [x] 1.1 In `tests/roadmap/test_step_commit_title.py`, write a test that calls the helper with the item title `docs(security): SECURITY.md says that the Valkey commands are not MCP tools`, the step title `Correct the Valkey paragraph in SECURITY.md` and the issue 2670, and asserts the exact title `docs(security): Correct the Valkey paragraph in SECURITY.md (#2670)`. Add the case of a step title that already ends with `(#2670)`, and the case of an item title with no prefix, which asserts `chore: Update SECURITY.md (#2670)`
  - Verification: `uv run devops ci test tests/roadmap/test_step_commit_title.py` fails on the base
- [x] 1.2 Add the public function that builds a step commit title in `src/devops_cli/roadmap/step_commit.py`. It reads the type and scope of the item title with `commit_type` and `commit_scope` from `src/devops_cli/roadmap/commit_title.py`, falls back to the type `chore` and no scope when `commit_type` gives none, appends the step title, and appends ` (#N)` only when the text does not already end with it
  - Verification: `uv run devops ci test tests/roadmap/test_step_commit_title.py` passes

## 2. Commit each task group with the formatted title

Reads: `src/devops_cli/roadmap/step_commit.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_step.py` (the inputs of a step carry the item title, and the commit uses the helper), `docs/roadmap/implement.md` (the form of the step commit title), `tests/roadmap/test_roadmap_implement_step_commit.py` (new), and the job suites whose un-prefixed titles are updated.

- [x] 2.1 In `tests/roadmap/test_roadmap_implement_step_commit.py`, write a case of a step of a `docs(security):` item that asserts the title of the commit the step makes is `docs(security): <step title> (#<issue>)`. The fallback of a fix step of an item with no prefix is proved by the existing `test_a_fix_step_commits_the_fix_with_the_tasks_as_they_were`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_commit.py` fails on the base
- [x] 2.2 Add a field to the inputs of a step that holds the item title, set it in `build_step_inputs` from the item it reads, and replace the title that the step gives its one commit with the helper that reads it, leaving the title of the archive commit as `docs(openspec): archive the change (#N)`. State the form of the step commit title in `docs/roadmap/implement.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_commit.py` passes
- [x] 2.3 Update the step titles that the tests hold to the formatted title: `chore: The first group (#1)` and `chore: Make check Static Analysis pass (#1)` in `tests/roadmap/test_roadmap_implement_step.py`, and `fix(roadmap): The first group (#1)`, `fix(roadmap): The second group (#1)`, `fix(roadmap): Make check <name> pass (#1)` and `fix(roadmap): Make check static pass (#1)` in `tests/roadmap/test_roadmap_implement_job.py`, `tests/roadmap/test_roadmap_implement_amend_job.py`, `tests/roadmap/test_roadmap_implement_job_scoped.py`, `tests/core/test_roadmap_implement_checks.py` and `tests/core/test_roadmap_implement_planned_run.py`
  - Verification: `uv run devops ci test tests/roadmap/ tests/core/test_roadmap_implement_checks.py tests/core/test_roadmap_implement_planned_run.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
