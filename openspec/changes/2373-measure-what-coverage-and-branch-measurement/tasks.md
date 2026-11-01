# Tasks

## 1. Run four coverage configurations and record medians

Reads: none. Changes: `openspec/changes/2373-coverage-cost-measurement/benchmark-results.md`.

- [ ] 1.1 Write a check that benchmark-results.md contains four configuration rows (no coverage, lines, lines and branches, lines with ctrace core), each with three runs of user-plus-system CPU time and wall time, and a median column. The file does not exist, so the check fails, and verify that `test -f openspec/changes/2373-coverage-cost-measurement/benchmark-results.md && grep -q 'median' openspec/changes/2373-coverage-cost-measurement/benchmark-results.md` fails on the base
- [ ] 1.2 Check uptime is under 2. For each of the four configurations, run uv run pytest with the gate options three times. Record user-plus-system CPU time and wall time for each run. Compute the median. Write the table to benchmark-results.md, and verify that `test -f openspec/changes/2373-coverage-cost-measurement/benchmark-results.md && grep -q 'median' openspec/changes/2373-coverage-cost-measurement/benchmark-results.md` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Time the serial coverage commands

Reads: none. Changes: `openspec/changes/2373-coverage-cost-measurement/benchmark-results.md`.

- [ ] 2.1 Write a check that benchmark-results.md contains a section with separate timings for coverage combine, coverage report --show-missing, and coverage xml, each with CPU and wall time. The section does not exist, so the check fails, and verify that `grep -q 'coverage combine' openspec/changes/2373-coverage-cost-measurement/benchmark-results.md && grep -q 'coverage report' openspec/changes/2373-coverage-cost-measurement/benchmark-results.md && grep -q 'coverage xml' openspec/changes/2373-coverage-cost-measurement/benchmark-results.md` fails on the base
- [ ] 2.2 Using the .coverage data files from the lines run, run coverage combine, coverage report --show-missing, and coverage xml each alone. Record the CPU and wall time of each. Append the results to benchmark-results.md, and verify that `grep -q 'coverage combine' openspec/changes/2373-coverage-cost-measurement/benchmark-results.md && grep -q 'coverage report' openspec/changes/2373-coverage-cost-measurement/benchmark-results.md && grep -q 'coverage xml' openspec/changes/2373-coverage-cost-measurement/benchmark-results.md` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. State the cost and apply the conditional change

Reads: none. Changes: `openspec/changes/2373-coverage-cost-measurement/design.md`.

- [ ] 3.1 Write a check that design.md states the cost of branch measurement in seconds of CPU time and job time, and if the report step is a large share, that the CI option change is recorded with the threshold unchanged. The file does not exist, so the check fails, and verify that `grep -q 'branch' openspec/changes/2373-coverage-cost-measurement/design.md && grep -q 'seconds' openspec/changes/2373-coverage-cost-measurement/design.md` fails on the base
- [ ] 3.2 Compute the difference between the lines and lines-and-branches medians. Write the cost in seconds of CPU and job time. If the report or combine step is a large share, record the lower-cost option and verify the coverage floor in pyproject.toml is unchanged. State that no threshold is lowered, and verify that `grep -q 'branch' openspec/changes/2373-coverage-cost-measurement/design.md && grep -q 'seconds' openspec/changes/2373-coverage-cost-measurement/design.md` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
