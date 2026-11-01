# Proposal

## Why

The owner asked on 2026-10-27 (the decision comment on #2356) whether measuring branches is worth its job time, as #2163 proposes. No clean number exists for what coverage costs the test job. Previous attempts were confounded by host load or changed three variables at once. #2373 measures the cost on a quiet host and reports it on #2163.

## What Changes

- Run four coverage configurations (no coverage, lines, lines+branches, lines+ctrace) three times each on an idle host and record median CPU and wall time
- Time the serial coverage commands (combine, report, xml) separately on the data of the lines run
- State the cost of branch measurement in seconds of CPU and job time
- If the report or combine step is a large share, test lower-cost --cov-report options without lowering any threshold
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-coverage-reports`: coverage-cost-benchmark-record, coverage-report-options-cost

## Impact

- Documents: `openspec/changes/2373-coverage-cost-measurement/benchmark-results.md`, `openspec/changes/2373-coverage-cost-measurement/design.md`

## Feasibility

- The premise is confirmed by openspec/changes/archive/2026-10-27-2356-coverage-floor-and-test-cost/design.md section 4, which states: 'The cost of branch measurement is not established. The owner asked for it.' and names #2373 as the issue that measures it.
- The same design.md records the gate command (pytest --cov=src --cov-report=term-missing --cov-report=xml), the 16-worker parallel setup, the 287 s gate time, and the failed same-day comparison (load average 10 to 39).
- The 568 s ctrace run changed three variables at once (core, contexts, branches), so it does not isolate the cost of branches.
- First checks the implementation runs: (1) uptime to confirm the host is idle (load under 2); (2) uv run pytest --collect-only -q to confirm the suite collects; (3) uv run coverage --version to confirm coverage.py is installed; (4) uv run pytest tests/test_cli_startup_imports.py --cov=src --cov-report=term-missing to confirm the coverage plugin loads.

## Existing Tool Considered

coverage.py (with pytest-cov) is already in use. The sysmon and ctrace cores, branch measurement, and the combine/report/xml commands are options of coverage.py. Nothing new is built.
