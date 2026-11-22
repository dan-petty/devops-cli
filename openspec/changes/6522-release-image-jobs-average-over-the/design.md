# Design

## Decisions

- **Extend the in-repo `devops ci job-time` check with a list of checks instead of writing a new script.**: The check already reads the runs, files one P0 issue, holds the report one time and makes no request on a dry run, so the change adds two entries and their cases.
- **Hold each release image job to the mean of 360 s.**: AGENTS.md rule 5 allows 5 min and 1 min of tolerance, and `CONST_CI_JOB_TIME_LIMIT_SECONDS` is that sum in the staged tree, so the release jobs take the bound that the test job takes.
- **Average over the last 10 completed release runs of `main`.**: The proof of the issue reads ten release runs, and release runs are few, so a longer window hides a recent regression for longer.
- **Measure `MCP Server Image` and `Runner Image` and leave `Service Image` out.**: The issue names the two jobs that breach the bound, and the `Service Image` mean is inside it.
- **Read the list when no option names a check, and one check when an option does.**: The daily job runs the command with no option, and the single-job use of `--job`, `--runs` and `--limit` and its cases stay as they are.
- **Read `release.yml` on `main` only.**: The release workflow runs on each push to `main`, so ten completed runs exist, and the release pull request runs the same workflow on its branch with no release.
- **Keep one alarm issue per job.**: The alarm line holds the job, the workflow and the branch, so a breach of one job updates its issue and a second job files its own, as the base requirement already says.
- **Rename the step of the `Test Job Duration` job and update the parity allowlist key in the same change.**: `tests/commands/test_ci.py` refuses a step of `ci.yml` that its allowlist does not name, so the workflow and the test change together.

## Rejected alternatives

- **Measure all three image jobs of the release workflow.**: The issue names `MCP Server Image` and `Runner Image`, and the `Service Image` mean is inside the bound, so a third entry would alarm on a job that passes.
- **Measure the release image jobs by hand over ten releases.**: A hand measurement holds no bound after the ten runs end, and AGENTS.md rule 5 asks for a check that reads the history.
- **Set the alarm of the release image jobs at a mean of 300 s.**: AGENTS.md rule 5 makes a check a P0 bug above 5 min plus 1 min of tolerance, and an alarm at 300 s is stricter than the rule and fires on normal variation.
- **Alarm on one run over 360 s.**: Rule 5 bounds the mean, and the existing check alarms on the mean of its runs, not on one run.
- **Use the 20-run window of the test job for the release image jobs.**: Release runs are few, so 20 runs delay the alarm of a new regression by many days.
- **Read only the last release run.**: One run is noise, and rule 5 bounds the average of the runs.
- **Run the check twice more from the workflow with `--workflow release.yml --job <name> --runs 10`.**: The daily job runs the command with no option, so two more steps leave the default run blind to the two jobs and add steps to the daily job; the list keeps one step and one read.
- **Write a new script for the two release image jobs.**: It duplicates the existing check, its alarm issue, its one-time report and its dry run, which the in-repo check already holds.
- **Add an external metrics stack with an exporter and Prometheus.**: An exporter, a Prometheus and alert routing add a service and a secret for a mean that one read of the Actions API gives.
