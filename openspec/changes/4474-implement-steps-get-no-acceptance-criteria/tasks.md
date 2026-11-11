# Tasks

## 1. Give the step the refined criteria and no comment

Kind: behavior. Reads: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/refine/refine.py`. Changes: `src/devops_cli/roadmap/implement/implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/__snapshots__/test_roadmap_implement_step.ambr`, `tests/fixtures/roadmap/issue_bodies/refined.md`, `tests/fixtures/roadmap/issue_bodies/form-with-criteria.md`, `tests/fixtures/roadmap/issue_bodies/no-section.md`.

- [x] 1.1 In `tests/roadmap/implement/test_roadmap_implement_step.py`, assert with three real body shapes that `issue_inputs` holds each refined requirement with its scenario lines and holds no HTML comment, and snapshot the whole text
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/implement/implement_step.py`, remove the top-level comment blocks of the body and add its `Requirement:` headings to the wanted sections of `issue_inputs`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step.py` passes

## 2. Documents

Kind: documents. Changes: `docs/roadmap/implement.md`.

- [x] 2.1 In `docs/roadmap/implement.md`, state that the criteria of the step hold the refined requirements and that the step removes the HTML comments of the body
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
