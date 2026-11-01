# Design

## Decisions

- **Run the benchmark on a local idle host rather than in CI**: The issue requires uptime under 2 before each run. CI runners are shared and cannot guarantee an idle host. A local host gives a clean number.
- **Use the median of three runs rather than the mean**: The median is robust to one outlier run. The issue names the median as the reported figure.
- **Time the serial commands separately after the parallel run**: The parallel run hides the cost of combine, report, and xml. Timing them alone isolates the serial tail that the issue asks about.
- **Include a spec delta on ci-coverage-reports**: The change potentially alters the --cov-report options of the test job, which is an observable devops command option. The rules state that a devops command option change carries a spec delta.

## Rejected alternatives

- **Run the benchmark in a CI job**: The issue requires uptime under 2 before each run. CI runners are shared and the 2026-10-27 attempt failed because the load average was 10 to 39 from other runs (design.md section 4).
- **Use the 568 s ctrace run as the branch cost**: The design.md states: 'Run 2 above took 568 s against 287 s, but it changes the ctrace core, the contexts and the branches together.' Three variables changed at once, so the number does not isolate the cost of branches.
- **Add a recurring CI job for this measurement**: The issue states: 'It is a one-time benchmark. The result is a table in the pull request description. No recurring job is added.' (proposed design, key questions).
