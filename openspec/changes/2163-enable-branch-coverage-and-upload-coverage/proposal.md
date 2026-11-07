# Proposal

## Why

Issue #2163: the coverage gate measures less than it can, and CI keeps no record of what it measured. `[tool.coverage.run]` sets no `branch` key, so a guard such as `if a or b: raise` counts as covered when one side runs, and line coverage cannot show that the other side has no test. CI writes `.data/coverage.xml` for diff-cover and then discards it, so a reviewer cannot see the per-file figures of a run without a new run. The change turns branch measurement on and keeps the report as an artifact.

## What Changes

- `pyproject.toml` sets `branch = true` in `[tool.coverage.run]`, so coverage.py measures both sides of each conditional in the gate, in the shards and in `devops ci coverage`.
- `.github/workflows/ci.yml` adds the step `Upload Coverage XML` to the job `test`, after `Changed-Line Coverage`, with `actions/upload-artifact` pinned by commit SHA, `retention-days: 7`, `include-hidden-files: true` and `if-no-files-found: warn`.
- The step runs with `if: always()` and the condition of the step that writes the report, so a failed changed-line gate still keeps `.data/coverage.xml`.
- `tests/invariants/test_agents_md_claims.py` holds the `[tool.coverage.run]` table to `branch = true` next to the floor it already reads.
- `tests/invariants/test_workflow_contracts.py` holds the upload step to its place, its pin and its inputs.
- `CONTRIBUTING.md`, `docs/TESTING.md` and `docs/SDLC.md` state that the floor counts lines and branches and that the job keeps the XML report for 7 days.
- The change carries a spec delta because `pyproject.toml` is a manifest and the job's artifacts are observable. `fail_under` stays at 85 and the 90% changed-line gate stays as it is.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `coverage-branch-measurement`: The coverage gate measures branches

### Modified Capabilities

- `ci-coverage-reports`: The aggregate job keeps the coverage XML as an artifact

## Impact

- Code: `pyproject.toml`, `.github/workflows/ci.yml`
- Documents: `CONTRIBUTING.md`, `docs/TESTING.md`, `docs/SDLC.md`
- Tests: `tests/invariants/test_agents_md_claims.py`, `tests/invariants/test_workflow_contracts.py`

## Feasibility

- The premise holds at the staging commit. `read_file pyproject.toml` lines 234-241 shows `pyproject.toml:234:[tool.coverage.run]`, `pyproject.toml:235:data_file = ".data/.coverage"`, `pyproject.toml:236:parallel = true` and no `branch` key, and `pyproject.toml:241:fail_under = 85`. The issue cites `pyproject.toml:197-202` from commit b170358e; the table has moved and holds the same two keys.
- The probe for the setting agrees: "The path `tool.coverage.run` is no file of the staging commit. No commit in the history deleted or renamed it." The key is a table of a file, not a path, so the probe reports no file and no removal, and `read_file` shows the table in `pyproject.toml`.
- The probe for the workflow agrees: "The path `ci.yml` is no file at the root of the staging commit. These files of the commit are candidates: `.github/workflows/ci.yml`. No commit in the history deleted or renamed it."
- The report is written only in the aggregate job. `read_file .github/workflows/ci.yml` lines 243-271 shows `Combine and Check Coverage` running `coverage combine` and `coverage report`, then `.github/workflows/ci.yml:256:- name: Changed-Line Coverage` with `.github/workflows/ci.yml:262:uv run coverage xml -q` and `.github/workflows/ci.yml:264:uv run diff-cover .data/coverage.xml --compare-branch="origin/${BASE_REF}" --fail-under 90 --format "markdown:${GITHUB_STEP_SUMMARY}" || status=$?`. No step of the job uploads `.data/coverage.xml`.
- The report exists only where that step runs. `.github/workflows/ci.yml:257:if: github.event_name == 'pull_request' && steps.changes.outputs.outside_plan != 'false'` holds the step to a pull request that is no plan-only change, and the job itself runs under `.github/workflows/ci.yml:191:if: ${{ !cancelled() && github.event_name != 'schedule' }}`. A push to main, a plan-only pull request and a failed Quality Gate step write no XML, so the upload warns rather than fails.
- The pin to reuse exists in the same file. `search_code upload-artifact` gives one hit, `.github/workflows/ci.yml:176:uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2`, and the step at lines 174-182 uploads `.data/.coverage` with `.github/workflows/ci.yml:180:include-hidden-files: true` and `retention-days: 7`. The report path also starts with a dot, so it needs the same input.
- The floor holds with branches on. #2373 measured 93.01% of lines and 90.75% of lines and branches on the same tree, so `fail_under = 85` passes and no threshold moves. The owner decision of 2026-10-27 drops the raise, and #2356 owns the floor.
- The time budget is close and stays a measurement, not a test. #3593 reports the last 20 runs of `Tests & Coverage` at 290 s on average against the 300 s limit. The pull request gives 5 runs before and 5 after, and the average after stays under 300 s and is compared with the 240 s target of #2356.
- #2373 is open and planned. Its change `openspec/changes/2373-measure-what-coverage-and-branch-measurement` measures the cost of branch measurement on an idle host, and its group 1 stops when `pyproject.toml` holds a `branch` key. It measures before this change merges; this change does not measure that cost.
- First checks against the real system: `uv run devops ci coverage` prints the combined line and branch total, read against `fail_under = 85`; `uv run devops ci --check --only actionlint,zizmor` lints the changed workflow; `uv run devops ci test tests/invariants/test_agents_md_claims.py tests/invariants/test_workflow_contracts.py` runs the two changed test modules.
- `uv run devops ci test <path>` needs a checkout of the repository: the tests read `pyproject.toml` and `.github/workflows/ci.yml` from the tree.
- `uv run devops ci` needs a checkout of the repository and a network: its `audit` and `outdated` rows fetch advisories and package versions from PyPI and npm.
- `uv run devops ci job-time` needs a network and a client of the GitHub Actions API: it reads the last 20 runs of the `Tests & Coverage` check from the API, as `docs/TESTING.md:168` states.
- The change fits one pull request.

## Existing Tool Considered

coverage.py and pytest-cov, which the project already uses, measure branches when `[tool.coverage.run]` sets `branch = true`, and `actions/upload-artifact`, already pinned in `.github/workflows/ci.yml` for the shard data, keeps the report. Nothing is built and no internal code is deleted.

## Dependencies

None.
