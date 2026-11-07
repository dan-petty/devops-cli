# Tasks

## 1. Measure branches in the coverage gate

Reads: `pyproject.toml`, `tests/invariants/test_agents_md_claims.py`. Changes: `pyproject.toml`, `tests/invariants/test_agents_md_claims.py`.

- [x] 1.1 Add `branch = true` to `[tool.coverage.run]` after `parallel = true` in `pyproject.toml`, and leave `fail_under = 85` and `data_file = ".data/.coverage"` as they are. In `tests/invariants/test_agents_md_claims.py`, next to the test that reads the coverage floor, add a test that loads `pyproject.toml` with `tomllib` and asserts the `[tool.coverage.run]` table equals `{"data_file": ".data/.coverage", "parallel": True, "branch": True}`. The test fails on the base because the table has no `branch` key
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md_claims.py` passes

## 2. Upload the coverage XML from the aggregate job

Reads: `.github/workflows/ci.yml`. Changes: `.github/workflows/ci.yml`.

- [x] 2.1 In `.github/workflows/ci.yml`, add the step `Upload Coverage XML` to the job `test`, after `Changed-Line Coverage`. Set `if: always() && github.event_name == 'pull_request' && steps.changes.outputs.outside_plan != 'false'`, `uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2`, and `with: name: coverage-xml`, `path: .data/coverage.xml`, `include-hidden-files: true`, `if-no-files-found: warn`, `retention-days: 7`. Add a comment that says the step keeps the report that `coverage xml` writes and that a run with no report warns
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor` passes

## 3. Hold the upload step in the workflow contract test

Reads: `.github/workflows/ci.yml`, `tests/invariants/test_workflow_contracts.py`. Changes: `tests/invariants/test_workflow_contracts.py`.

- [x] 3.1 Add a test to `tests/invariants/test_workflow_contracts.py` that loads `.github/workflows/ci.yml`, takes the steps of the job `test`, and asserts that a step named `Upload Coverage XML` comes after the step named `Changed-Line Coverage`. Assert that its `uses` is `actions/upload-artifact` with a 40-character commit SHA, that its `if` is `always() && github.event_name == 'pull_request' && steps.changes.outputs.outside_plan != 'false'`, and that its `with` equals `{"name": "coverage-xml", "path": ".data/coverage.xml", "include-hidden-files": True, "if-no-files-found": "warn", "retention-days": 7}`. Assert that the `Changed-Line Coverage` step still runs `uv run coverage xml` before `diff-cover .data/coverage.xml`, so the step that reads the report is unchanged
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py` passes

## 4. State the branch measurement and the kept report

Reads: `CONTRIBUTING.md`, `docs/TESTING.md`, `docs/SDLC.md`, `pyproject.toml`. Changes: `CONTRIBUTING.md`, `docs/TESTING.md`, `docs/SDLC.md`.

- [x] 4.1 Change the floor sentence of `CONTRIBUTING.md` and of `docs/TESTING.md` to say that `devops ci` enforces 85% of the lines and branches of `src/`, keeping the figure once in each document so the test that reads `fail_under` still finds one statement per file. In `docs/SDLC.md`, state that `[tool.coverage.run]` sets `branch = true` and that the job `Tests & Coverage` keeps `.data/coverage.xml` as an artifact with a 7-day retention, beside the step that writes it
  - Verification: `$ uv run devops ci` passes
- [x] 4.2 Edit `CONTRIBUTING.md`, `docs/TESTING.md` and `docs/SDLC.md` to state that the floor counts lines and branches and that the job keeps the XML report for 7 days
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: `pyproject.toml` sets `branch = true`.
- Group 1: ~~[ ] `fail_under` is the whole percentage that CI measures with branches, and at least 90. The pull request gives the measured figure.~~ (Dropped: #2356.)
- Group 2: The `Tests & Coverage` job uploads `.data/coverage.xml` as an artifact. The step passes `zizmor` and `actionlint`.
- Pending person: The pull request gives the job time of 5 runs before and 5 runs after. The average after is under 300 s., The times come from runs of the changed workflow on GitHub, which a person reads and writes in the pull request body; no group changes a file for them.
- Group 3: diff-cover still reads `.data/coverage.xml` (#1743 keeps it in CI).
- Group 4: `uv run devops ci` passes.
