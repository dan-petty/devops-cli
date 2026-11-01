## Problem or Motivation

The owner asked on 2026-10-27 (the decision comment on #2356) whether measuring branches is worth its job time, as #2163 proposes. No clean number exists for what coverage costs the test job.

What is known, from #2356 on 2026-10-27 (16 CPUs, Python 3.14):

- The gate runs `pytest --cov=src --cov-report=term-missing --cov-report=xml` with the default `sysmon` core, with `parallel = true`: each of 16 workers writes a data file, and the controller combines them and prints a report for 560 files after the last test. That work is serial.
- Line coverage is 93.01%. With branches, the figure is 90.75% (19,776 of 23,918 branches).
- One run with the `ctrace` core, per-test contexts and branches took 568 s, against 287 s for the gate row. That run changes three things at once, so it does not give the cost of branches.
- A try to compare the suite with and without coverage on the same day failed. The host had a load average of 10 to 39 from other runs. The suite without coverage took 3,540 s of CPU in that try, and a cost of coverage cannot be told from the noise of that load. Two of the coverage runs also measured nothing (0.00% coverage), so their numbers were dropped.

This issue is a sub-issue of #2356.

## Proposed Solution & Architectural Design

Measure, on an idle host (`uptime` under 2 before each run), CPU time (user plus system) and wall time, three runs of each configuration, with the options of the gate:

| Configuration | Options |
| :--- | :--- |
| no coverage | none |
| lines | `--cov=src --cov-report=term-missing --cov-report=xml` |
| lines and branches | the same, with `--cov-branch` |
| lines, `ctrace` core | the same as lines, with `COVERAGE_CORE=ctrace` |

Then time the serial end of the run on the data of the "lines" run: `coverage combine`, `coverage report --show-missing` and `coverage xml`, each alone.

Report the table in the pull request, with the median of each configuration, and say what the branch measurement of #2163 costs in seconds of CPU and of job time. Then, from the numbers:

- if the report or the combine step is a large share, test `--cov-report=` options that cost less (for example, no `term-missing` on the runner, since the XML holds the lines);
- if branches cost much, say so on #2163 for the owner to decide. The owner sets thresholds, not this issue.

**Acceptance:** the table exists with three runs for each configuration on an idle host, the cost of branches is stated in seconds, and a change, if one is made, lowers the CPU time of the "lines" configuration without lowering any threshold.

## Target Subsystem

SDLC, Git & PR Governance

## Existing Tool Considered

- **`coverage.py`** and **`pytest-cov`** are in use. The core (`sysmon`, `ctrace`) and branch measurement are options of `coverage.py`.
- **`coverage combine/report/xml`** commands give the time of the serial end. Nothing new is built.


Source: https://github.com/dan-petty/devops-cli/issues/2356

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The owner needs a clean number for what coverage and branch measurement cost the CI test job. Previous attempts were confounded by host load or changed three variables at once. This issue measures CPU time and wall time for four coverage configurations on an idle host, times the serial coverage commands separately, and states the cost of branch measurement in seconds.

### Acceptance criteria
- Criterion 1: A table of median CPU time and wall time exists for four configurations, each from three runs on an idle host.
  Verification: The pull request description contains a table with rows for no coverage, lines, lines and branches, and lines with ctrace core. Each row shows the median CPU time and wall time from three runs. The host uptime was under 2 before each run.
- Criterion 2: The cost of branch measurement is stated in seconds of CPU time and job time.
  Verification: The pull request description states the difference in CPU time and wall time between the 'lines' and 'lines and branches' configurations in seconds.
- Criterion 3: The serial end of the coverage run is timed as separate commands.
  Verification: The pull request description contains separate timing for `coverage combine`, `coverage report --show-missing`, and `coverage xml`, each run alone.
- Criterion 4: If a change is made to lower cost, it does not lower any coverage threshold.
  Verification: The pull request shows the 'lines' configuration CPU time is lower after the change. The coverage floor value is unchanged.

### Key questions
- **What options does the gate use for coverage?**: The gate runs `pytest --cov=src --cov-report=term-missing --cov-report=xml` with the default `sysmon` core and `parallel = true`. Each of 16 workers writes a data file, and the controller combines them and prints a report for 560 files. [sources: openspec/changes/archive/2026-10-27-2356-coverage-floor-and-test-cost/design.md]
- **Is the measurement a one-time benchmark or a recurring CI job?**: It is a one-time benchmark. The result is a table in the pull request description. No recurring job is added. (proposed)
- **Does the measurement require a code change in this repository?**: No code change is required for the measurement itself. It runs existing pytest and coverage commands with different flags. A change to CI options is made only if the numbers show a large share in the report or combine step. (proposed)
- **What is the known cost data from the 2026-10-27 runs?**: Line coverage is 93.01%. With branches, the figure is 90.75% (19,776 of 23,918 branches). One run with the ctrace core, per-test contexts and branches took 568 s against 287 s for the gate row, but it changes three things at once. A same-day comparison failed because the host load average was 10 to 39. [sources: openspec/changes/archive/2026-10-27-2356-coverage-floor-and-test-cost/design.md]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "fdfdb518800335004ba469dc2e468dd991565936a4513c67d3a4365efdcb00c3", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "476b5d365b680ec2a54d45784566265dff8e1f5385f77fea9d15e8fd59ad97d0", "stage.branch": "perf/2373-measure-what-coverage-and-branch-measurement", "stage.file_cap": null, "stage.groups": "[[\"Run four coverage configurations and record medians\", 3979], [\"Time the serial coverage commands\", 4020], [\"State the cost and apply the conditional change\", 3983]]", "stage.needs_split": null, "stage.pr": "2987", "stage.ready": "2987", "stage.sha": "dc62f43a85a26b9d754a0357d404600340cd9399"} -->
