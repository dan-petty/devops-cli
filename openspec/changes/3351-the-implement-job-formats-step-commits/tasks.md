# Tasks

## 1. Build the step commit title from the item title

Reads: `CONTRIBUTING.md`, `src/devops_cli/roadmap/commit_title.py`, `src/devops_cli/roadmap/pull_form.py`. Changes: `src/devops_cli/roadmap/step_commit.py` (new), `tests/roadmap/test_step_commit_title.py` (new).

- [ ] 1.1 In `tests/roadmap/test_step_commit_title.py`, write a test that calls the helper with the item title `docs(security): SECURITY.md says that the Valkey commands are not MCP tools`, the step title `Correct the Valkey paragraph in SECURITY.md` and the issue 2670, and asserts the exact title `docs(security): Correct the Valkey paragraph in SECURITY.md (#2670)`. Add the case of a step title that already ends with `(#2670)`, and the case of an item title with no prefix, which asserts `chore: Update SECURITY.md (#2670)`
  - Verification: `uv run devops ci test tests/roadmap/test_step_commit_title.py` fails on the base
- [ ] 1.2 Add the public function that builds a step commit title in `src/devops_cli/roadmap/step_commit.py`. It reads the type and scope of the item title with `commit_type` and `commit_scope` from `src/devops_cli/roadmap/commit_title.py`, falls back to the type `chore` and no scope when `commit_type` gives none, appends the step title, and appends ` (#N)` only when the text does not already end with it
  - Verification: `uv run devops ci test tests/roadmap/test_step_commit_title.py` passes

## 2. Commit each task group with the formatted title

Reads: `src/devops_cli/roadmap/step_commit.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_step.py` (the inputs of a step carry the item title, and the commit uses the helper), `tests/roadmap/test_roadmap_implement_step_commit.py` (new), `tests/roadmap/test_roadmap_implement_step.py` (the two un-prefixed titles updated).

- [ ] 2.1 In `tests/roadmap/test_roadmap_implement_step_commit.py`, write a case of a step of a `docs(security):` item that asserts the title of the commit the step makes is `docs(security): <step title> (#<issue>)`, and a case of a fix step of an item with no prefix that asserts `chore: Make check <name> pass (#<issue>)`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_commit.py` fails on the base
- [ ] 2.2 Add a field to the inputs of a step that holds the item title, set it in `build_step_inputs` from the item it reads, and replace the title that the step gives its one commit with the helper that reads it, leaving the title of the archive commit as `docs(openspec): archive the change (#N)`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_commit.py` passes
- [ ] 2.3 Update the two assertions in `tests/roadmap/test_roadmap_implement_step.py` that hold the un-prefixed titles `The first group (#1)` and `Make check Static Analysis pass (#1)` to `chore: The first group (#1)` and `chore: Make check Static Analysis pass (#1)`, the item of the fixture having no prefix
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
