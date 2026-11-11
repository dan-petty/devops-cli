# Tasks

## 1. Row of a scoped update

Kind: behavior. Reads: `src/devops_cli/github/request_scope.py`, `src/devops_cli/server/service.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_run_scoped_update.py`.

- [x] 1.1 Write `test_the_model_requests_of_a_scoped_intake_carry_the_intake_row`, and watch it fail with `row` `other` on the request, token and spend series
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Run the runner of the scoped update in `request_scope(row=update.job)`
  - Verification: `$ uv run pytest -q tests/roadmap/test_roadmap_run_scoped_update.py`

## 2. Documents

Kind: documents. Reads: `docs/TELEMETRY.md`. Changes: `src/devops_cli/github/request_scope.py`, `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`.

- [x] 2.1 Say in the row text and in the `request_scope` docstring that a scoped update names its job as the row, and generate the documents
  - Verification: `$ uv run devops docs generate --check`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
