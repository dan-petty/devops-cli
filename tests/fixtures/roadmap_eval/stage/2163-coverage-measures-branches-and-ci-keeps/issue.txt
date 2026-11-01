### Owner decision, 2026-10-27

The owner chose the direction of #2356 for the coverage floor: a lower global floor (85%) and a gate on the changed lines. So the rise of `fail_under` to the measured total is dropped from this issue, and the three places that asked for it are struck through below. Do not raise `fail_under` here.

What stays: the measurement of branches and the upload of `.data/coverage.xml` as an artifact. Both are independent of the floor. The measurement of branches adds job time, and #2356 wants the `Tests & Coverage` job at or below 240 s, so the time check below (the average after the change stays under 300 s) is a minimum, and the pull request also reports the average against 240 s.

### Problem

The coverage gate measures less than it can, and CI keeps no record of what it measured.

- Branch coverage is off: `[tool.coverage.run]` sets no `branch = true`. A guard such as `if a or b: raise` counts as covered when one side runs. Line coverage cannot show that the other side has no test.
- `fail_under = 90`, while the suite measures 92.66% of lines in CI at f4d7066b. A change can drop about 2.6 points of coverage and still pass.
- CI writes `.data/coverage.xml` for diff-cover and then discards it. No artifact keeps it, so a reviewer cannot see the per-file figures of a run without a new run.

### Proposed solution

- `[tool.coverage.run]` sets `branch = true`. Coverage 7.16.1 on Python 3.14.7 measures branches with `sys.monitoring`.
- ~~`fail_under` rises to the whole percentage that CI measures with branches on, and never below 90. The owner's rule allows a raise and forbids a drop.~~ (Dropped: #2356.)
- The `Tests & Coverage` job uploads `.data/coverage.xml` with `actions/upload-artifact`, pinned by commit SHA, with a short retention.

### Feasibility and time

- The `Tests & Coverage` job took 245-307 s in the last 8 successful runs of `ci.yml` on main (2026-10-24, runs 40108255492 to 40125840892), 284.5 s on average. Two runs were above 300 s. A job that averages more than 5 minutes is a P0 bug.
- The pull request measures the job over 5 CI runs before and after the change. If branch measurement takes the average to 300 s or more, the item waits for a change that makes the suite faster, such as the git fake of #2146, and does not drop a check.
- ~~The total with branches can be lower than the line total. If it is below 90, the item waits for the coverage issues of the same audit and does not lower `fail_under`.~~ (Dropped: #2356.)

### Existing tool considered

coverage.py and pytest-cov, which the project already uses, measure branches. `actions/upload-artifact` keeps the report. Nothing is built.

### Evidence

At b170358e:
- `pyproject.toml:197-202`: `[tool.coverage.run]` holds `data_file` and `parallel`, and `fail_under = 90`.
- `.github/workflows/ci.yml:80-120`: the job runs the gate and diff-cover, and uploads no coverage artifact.
- `.data/agent/scratch/audit-coverage/ci-test-job.log`: the CI coverage total of 92.66% at f4d7066b.

### Acceptance criteria

- [ ] `pyproject.toml` sets `branch = true`.
- ~~[ ] `fail_under` is the whole percentage that CI measures with branches, and at least 90. The pull request gives the measured figure.~~ (Dropped: #2356.)
- [ ] The `Tests & Coverage` job uploads `.data/coverage.xml` as an artifact. The step passes `zizmor` and `actionlint`.
- [ ] The pull request gives the job time of 5 runs before and 5 runs after. The average after is under 300 s.
- [ ] diff-cover still reads `.data/coverage.xml` (#1743 keeps it in CI).
- [ ] `uv run devops ci` passes.

Related: #1743 (the local gate stops writing the XML report; CI keeps it).


Source: https://github.com/dan-petty/devops-cli/issues/1743

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=2ae3772423fe264ad4fd2d9ee6681535015bface -->
## Proposed design

### Problem statement
CI writes `.data/coverage.xml` for diff-cover and then discards it. A reviewer cannot see the per-file coverage figures of a run without a new run. This issue uploads the file as a CI artifact. The branch coverage part of the original scope is blocked. The `Tests & Coverage` job already averages 376 s, over the 300 s limit. Adding branch measurement would make the time worse.

### Acceptance criteria

### Requirement: Upload coverage XML as artifact
The `Tests & Coverage` job SHALL upload `.data/coverage.xml` as a CI artifact using `actions/upload-artifact` pinned by commit SHA, with `include-hidden-files: true` and a retention period.

#### Scenario: Artifact available after run
- **WHEN** The `Changed-Line Coverage` step completes successfully
- **THEN** An artifact containing `.data/coverage.xml` is available for download

### Requirement: Upload gated on coverage step
The upload step SHALL run on the outcome of the `Changed-Line Coverage` step, not on `always()`.

#### Scenario: Upload skipped when coverage fails
- **WHEN** The `Changed-Line Coverage` step fails
- **THEN** The upload step does not run

### Requirement: Lint checks pass
The new upload step SHALL pass `zizmor` and `actionlint`.

#### Scenario: Lint and security checks pass
- **WHEN** `uv run devops ci --check --only lint,format,actionlint,zizmor` runs
- **THEN** The command exits 0

### Requirement: diff-cover unchanged
The `Changed-Line Coverage` step SHALL still read `.data/coverage.xml`.

#### Scenario: diff-cover reads the XML
- **WHEN** The `Changed-Line Coverage` step runs
- **THEN** It reads `.data/coverage.xml` and reports changed-line coverage

### Requirement: Full gate passes
`uv run devops ci` SHALL pass with the artifact upload step in place.

#### Scenario: Full CI gate passes
- **WHEN** `uv run devops ci` runs in a clean environment
- **THEN** The command exits 0

### Existing Tool Considered
No check has run. `actions/upload-artifact` v7.0.2 covers the need. It skips hidden files by default, so `include-hidden-files: true` is required for `.data/coverage.xml`. Nothing is built.

### Key questions
- **Should this issue be split into artifact upload and branch coverage?**: Yes. The person re-scoped the issue: artifact upload is ready now; branch coverage is blocked by #2369, #2371, #2373 because the job already averages 376 s, over the 300 s limit. (a person decides)
- **Should the upload step run on `always()` or on the coverage step's outcome?**: Run on the coverage step's outcome, not on `always()`. Give the `Changed-Line Coverage` step an id and reference it. (proposed)
  - Chosen: Run on step outcome. The person directed this. It avoids uploading a stale or partial report when the coverage step fails.
  - Rejected: Run on always(). Would upload even when the coverage step fails, giving a misleading artifact.

### Open questions
- Should this issue be split into artifact upload and branch coverage? (a person decides)
- What version of `actions/upload-artifact` should be used, and does it handle hidden files? (missing verified source)
- What is the current average time of the `Tests & Coverage` job? (missing verified source)
- What blocks the branch coverage part? (missing verified source)

### Fit
Needs splitting into 2 items:
1. Upload `.data/coverage.xml` as a CI artifact (ready now)
2. Enable `branch = true` in `[tool.coverage.run]` (blocked by #2369, #2371, #2373)

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P2-Medium", "Status": "New", "Value": "High", "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "8b02518e245d1551e137b924528b3e991f64373ff4abac11c39be81b7349a606", "refine.failed_body_hash": null, "refine.needs_split": "true", "refine.next_step": "person", "refine.section_hash": "d2df53d4dfdc2b42c144151eb72a47a52f0573e1ca82626e25104a1fc47b5841", "stage.branch": "ci/2163-coverage-measures-branches-and-ci-keeps", "stage.file_cap": null, "stage.groups": "[[\"Enable branch coverage in pyproject.toml\", 3642], [\"Upload coverage XML as CI artifact\", 3730]]", "stage.needs_split": null, "stage.pr": "2980", "stage.ready": "2980", "stage.sha": "81471511d663dd548146193367729bb58792913f"} -->
