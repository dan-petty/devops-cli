# Proposal

## Why

#2163 reports that the coverage gate measures only lines, not branches, so a guard like `if a or b: raise` counts as covered when one side runs. CI also discards .data/coverage.xml after diff-cover reads it, so a reviewer cannot see per-file figures without a new run.

## What Changes

- pyproject.toml sets `branch = true` in [tool.coverage.run] so coverage.py measures both sides of each conditional
- .github/workflows/ci.yml adds an upload-artifact step to the Tests & Coverage job that keeps .data/coverage.xml with a 7-day retention
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-coverage-reports`: branch-coverage-measurement, coverage-xml-artifact-upload

## Impact

- Code: `pyproject.toml`, `.github/workflows/ci.yml`

## Feasibility

- Confirmed: pyproject.toml line 229 shows `data_file = ".data/.coverage"` in [tool.coverage.run] with no `branch` key, matching the issue's claim at pyproject.toml:197-202.
- Confirmed: .github/workflows/ci.yml has no upload-artifact step for .data/coverage.xml; the job runs diff-cover and ends without keeping the file.
- The Tests & Coverage job took 245-307 s in the last 8 runs (284.5 s average). Branch measurement adds time. The 300 s average limit is the hard bound; the PR also reports against the 240 s target from #2356.
- First checks the implementation runs: `uv run devops ci test` to verify the suite passes with branch coverage on; `uv run devops ci --check --only lint,format,actionlint,zizmor` to verify the workflow passes actionlint and zizmor.

## Existing Tool Considered

coverage.py and pytest-cov, which the project already uses, measure branches when `branch = true` is set. `actions/upload-artifact` keeps the report. Nothing is built.
