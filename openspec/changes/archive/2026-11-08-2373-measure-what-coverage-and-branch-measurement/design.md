# Design

## Decisions

- **Pin four CPUs and remove idle-host gate.** Pin each run to four CPUs with `taskset -c 0-3` and run `-n 4`, matching the CI runner. Record the load average before each run, and do not stop or discard runs because of host load.
- **Compare four configurations on one shard across three interleaved rounds.** Test no coverage, lines (`--cov=src --cov-report=`), lines and branches (`--cov=src --cov-report= --cov-branch`), and lines with the `ctrace` core (`COVERAGE_CORE=ctrace`). Interleaving distributes any host load changes evenly across all configurations.
- **Use CPU time as the primary metric.** User plus system CPU time isolates execution cost from host noise. Wall time gives the job-time impact for one shard. The whole-job CPU cost is four times the per-shard difference.
- **Time serial coverage commands separately on shard data files.** Time `coverage combine`, `coverage report --show-missing`, and `coverage xml` on four shard coverage data files. Note that `coverage xml` runs only on pull requests.
- **Define 15 s as a large share for serial execution.** The CI test budget is 300 s; 5% is 15 s. State whether the combine and report steps reach 15 s and whether a follow-up issue is needed.
- **Document results in `docs/TESTING.md`.** Add a `### Coverage cost` subsection after `### Coverage`. Link the document from the pull request and post the branch cost on #2163.
- **Keep thresholds and gate options unchanged.** This measurement changes no gate option, floor, or check command. Any option modification is left to a follow-up issue.
- **Set `skip_specs: true`.** The documentation change alters no observable runtime behavior or public command interface.

## Rejected alternatives

- **Idle-host gate requiring load under 2.** Rejected because the shared host load remains above 3, causing the previous attempt to stall.
- **Unpinned full-suite runs.** Rejected because unpinned wall time fluctuates significantly under varying host load.
- **Spec delta for benchmark record.** Rejected because benchmark documentation is not observable consumer behavior that tests under `tests/` assert offline.
- **Lowering options or thresholds in this pull request.** Rejected because acceptance criteria require no threshold to be lowered and any option change to be handled in a follow-up issue.
