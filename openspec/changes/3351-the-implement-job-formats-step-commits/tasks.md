# Tasks

## 1. Build the step commit title from the item title

Reads: `CONTRIBUTING.md`, `src/devops_cli/roadmap/commit_title.py`, `src/devops_cli/roadmap/pull_form.py`. Changes: `src/devops_cli/roadmap/step_commit.py` (new), `tests/roadmap/test_step_commit_title.py` (new).

- [ ] 1.1 In `tests/roadmap/test_step_commit_title.py`, write a test that calls the helper with the item title `docs(security): SECURITY.md says that the Valkey commands are not MCP tools`, the step title `Correct the Valkey paragraph in SECURITY.md` and the issue 2670, and asserts the exact title `docs(security): Correct the Valkey paragraph in SECURITY.md (#2670)`. Add the case of a step title that already ends with `(#2670)`, and the case of an item title with no prefix, which asserts `chore: Update SECURITY.md (#2670)`
  - Verification: `uv run devops ci test tests/roadmap/test_step_commit_title.py` fails on the base
- [ ] 1.2 Add the public function that builds a step commit title in `src/devops_cli/roadmap/step_commit.py`. It reads the type and scope of the item title with `commit_type` and `commit_scope` from `src/devops_cli/roadmap/commit_title.py`, falls back to the type `chore` and no scope when `commit_type` gives none, appends the step title, and appends ` (#N)` only when the text does not already end with it
  - Verification: `uv run devops ci test tests/roadmap/test_step_commit_title.py` passes

## 2. Commit each task group with the formatted title

Reads: `src/devops_cli/roadmap/step_commit.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_implement_step_commit.py` (new).

- [ ] 2.1 In `tests/roadmap/test_roadmap_implement_step_commit.py`, write a case of a step of a `docs(security):` item that asserts the title of the commit the step makes is `docs(security): <step title> (#<issue>)`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_commit.py` fails on the base
- [ ] 2.2 Replace the title that the step gives its one commit with the value of the helper, and leave the title of the archive commit as `docs(openspec): archive the change (#N)`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_commit.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
