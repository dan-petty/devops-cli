# The success of the roadmap jobs

Each roadmap job gets a job grade from its measured success, and each grade has one action. The owner tunes the caps and the limits of a roadmap job only after the job holds 80% success. This page gives the measure of each job, the log line that counts it, the queries that read it, the job grades and the 80% rule. The rules that a test checks are in the specs named at the end of this page.

## Why a log line and not a counter

The counters of the jobs give no common ratio. Each job counts other results, the review of refine counts no approval, and the alternatives check counts no refused reply. Before release 0.116.1, a new series of a counter also lost its first count (#4684). A log line holds the counts of each attempt, such as its tokens and its gate returns, which a metric label cannot hold for each item. So each job writes one log line for each attempt, and Loki counts the lines. Prometheus recording rules can give the same ratio later.

## The result line

The roadmap Service writes one line for each attempt of a job:

```text
roadmap job result: job=<job> repo=<owner/repo> item=#<n> result=<result> success=<true|false> class=<class> infra=<true|false> <count>=<n> ... version=<version>
```

- `job` is `stage`, `implement`, `refine`, `refine_judge`, `alternatives`, `intake` or `fix_plan`.
- `success` is `true` when the result is the intended result of the job (table below).
- `class` is the failure class of `roadmap/failure.py`, or `none`.
- `infra` is `true` for a class that a cut of the infrastructure gives: `provider`, `ci_infra`, `oom` and `limit_reached`. The ratio of the dashboard counts these attempts as failures and shows their share apart. The job grade leaves them out of `p`.
- The counts and the names of the job follow, and the devops-cli version ends the line, so a query can compare two images.

A line holds no text of an issue, of a model or of a log. Each value is a number or a fixed name. The writer changes a value with another character than a letter, a digit, `_`, `-` or `.` to `other`. `src/devops_cli/roadmap/job_result.py` holds the form and the table below.

## The attempt and the intended result of each job

| Job | Where the line comes from | Results | Intended result | Counts and names |
| :--- | :--- | :--- | :--- | :--- |
| `stage` | Each item that a round tried. A left-out item writes no line. | `staged`, `needs_split`, `failed`, `degenerate` | `staged`: the plan pull request is open. | `plan_calls`, `gate_returns`, `verify_rounds`, `tokens`, `seconds` |
| `implement` | Each runner Job that ended, when the `implement` row reports it. | `ready`, `yielded`, `returned`, `stopped` | `ready`: the pull request is ready. | `repair_rounds`, `tokens`, `seconds` |
| `refine` | Each item that a round refined. | The next step of the item, or `error` for a failed model call or write | `ready`, `person`, `split` or `blocked` | none |
| `refine_judge` | Each review of the proposal for an item that a bot opened that calls the model. A kept approval writes no line. | `approved`, `refused` | `approved` | `findings` |
| `alternatives` | Each check that the round wrote, and each failed check. | The verdict, `refused` or `failed` | Each verdict | `searches`, `reason` (the skip class, or the code of the error) |
| `intake` | Each candidate that a round wrote. | `placed`, `duplicate`, `skipped`, `failed` | `placed` and `duplicate` | none |
| `fix_plan` | Each attempt of the step `fix-plan` on a plan pull request with `plan/needs-fix`. A plan that the selection or the branch check leaves out writes no line, and a plan that the plan reader refuses (`unreadable`) writes no line, because the defect is in the writer or the reader of the plan. | `revised`, `cleared`, `regated`, `dismissed`, `unchanged`, `stopped`, `failed`, `timeout` | `revised` and `cleared`: the step pushed a repair whose last review has fewer open findings than the review of the head in the same attempt. `regated`, `dismissed`, `unchanged`, `stopped`, `failed` and `timeout` repair no finding of that review. | `plan_calls`, `gate_returns`, `verify_rounds`, `tokens`, `seconds`, `comment` (the open findings that the last plan comment lists), `before` (the review of the head, only when it ran), `after` (the last review of the revision, only when one ran). A stop adds `stop`, and a failure and a `timeout` add `step`. |

A `stage` item that is staged with an open finding of the review is `failed` with the class `plan_defect`. An `implement` Job that recorded no result, such as a pod that the kernel killed, is `stopped`. Its `seconds` run from the start of its pod to its end, and are 0 when the Job is gone.

Some attempts write no line:

- A stop of the Service ends the round, and the attempt in progress writes no line.
- An alternatives check whose body a person changed since the read writes no line. The next round checks the item again.
- A refine item that a person or another job changed since the read writes no line. Refine does not write the item, the round does not fail, and the next round reads the item again.

A change that adds a cap extension to a job adds the count `extensions` to the line of that job.

## The query

The dashboard `devops-cli Telemetry` has the row `Roadmap Job Success`. It shows the 7-day ratio of each job against the line at 0.80, the attempts of each job with `too few` under 30, the share of the infrastructure cuts, and the ratio at each daily check. Each panel reads the result lines with this base:

```logql
{namespace="devops", app_kubernetes_io_name="roadmap-service"} |= "roadmap job result:"
  | json message | line_format "{{.message}}"
  | regexp `^roadmap job result: job=(?P<roadmap_job>\S+) repo=\S+ item=\S+ result=(?P<result>\S+) success=(?P<success>\S+) class=(?P<failure_class>\S+) infra=(?P<infra>\S+)`
```

The label is `roadmap_job`, because the stream already has the label `job`. The ratio of the last 7 days is:

```logql
(
  sum by (roadmap_job) (count_over_time(<base> | success="true" [7d]))
    or on (roadmap_job) (sum by (roadmap_job) (count_over_time(<base> [7d])) * 0)
)
  / sum by (roadmap_job) (count_over_time(<base> [7d]))
```

The `or on (roadmap_job)` part gives 0 successes to a job that has attempts and no success. Without it, the division drops that job, and a job at 0% looks the same as a job with no attempts.

`devops roadmap eval grades` reads the same lines with LogQL metric instant queries, so no line limit applies. Its base also takes `repo` and `version` from the line, and each query groups by the job and the repository. `--dry-run` prints each query and sends no request.

## The job grades

Each roadmap workflow gets a job grade from its result lines: `100`, `90`, `80`, `70`, `60`, `<60` or `too few`. Each grade has one action, from the owner request of 2026-11-12. A job grade is not the band of a decision point (ADR 0020). `devops roadmap eval grades` prints the grade of each workflow and repository, and `--format json` gives the same report to an agent.

The ratio `p` is the successes divided by the attempts with `infra=false`. An infrastructure cut is not a fault of the workflow, so `p` does not count it, and one outage does not give each workflow the action of `<60`. The report shows the ratio of all attempts and the infrastructure share beside `p`.

`src/devops_cli/roadmap/job_grade.py` holds the grade table, and `devops docs generate` writes it here:

<!-- JOB_GRADES_START -->

| Grade | Rule | Name | Action | Efficiency work |
| :--- | :--- | :--- | :--- | :--- |
| `100` | every attempt is a first pass | Check the measure | Look for measure defects or bugs. Look for ways to tighten gates, restrictions and correction suggestions. | optimize |
| `90` | p ≥ 0.90 | Well performing | Apply routine updates and refinements. Give priority to new features. | optimize |
| `80` | 0.80 ≤ p < 0.90 | Acceptable | Find the leading failure modes. Give priority to fixes and fixer jobs that increase success. | optimize |
| `70` | 0.70 ≤ p < 0.80 | Degraded | Find the leading causes of failure, with high priority. | report only |
| `60` | 0.60 ≤ p < 0.70 | Ineffective | Look for implementation alternatives, or serious defects that a fix can correct. | report only |
| `<60` | p < 0.60 | Coin flip | Re-architect the workflow. | report only |
| `too few` | fewer than 30 attempts | Not graded | Show p and the interval. Give no grade. | report only |

<!-- JOB_GRADES_END -->

- **Interval.** The report gives the Wilson 95% interval of `p` (statsmodels `proportion_confint`), the point grade of `p` and the grades of the two bounds. For example, 22 successes in 25 attempts give `p` 0.88, the interval [0.70, 0.96], the point grade 80 and the range 70 to 90. The grade is `too few`, because 25 attempts are fewer than 30.
- **First pass.** A first pass is a success with no fix round. The grade `100` needs a first pass for each attempt. Three lines hold the counts of the rule (`FIRST_PASS_LIMITS` in `src/devops_cli/roadmap/job_result.py`): `stage` (`plan_calls` ≤ 1, `gate_returns` = 0, `verify_rounds` ≤ 1), `implement` (`repair_rounds` = 0) and `fix_plan` (`gate_returns` = 0, `verify_rounds` ≤ 1, `after` = 0). The line of another job has no count of its fix rounds, so its first pass is not known, and it cannot get the grade `100`.
- **Windows.** The 7-day window gives the grade. The report also shows the attempts and the successes of the last 24 hours and of the last 6 hours. 5 attempts or more with no success in 6 hours give the signal `broken`. An infrastructure share over 20% of 10 attempts or more in 24 hours gives the signal `infra`, and not a grade.
- **Versions.** The report shows each devops-cli version that has 10 attempts or more in the window.
- **Failure classes.** The report shows the 3 largest failure classes of the attempts with `infra=false`.
- **Efficiency.** For a job whose line has `tokens` and `seconds`, the report shows the median, the p90 and the max of each attempt, and the tokens and the seconds of all attempts divided by the successes. At the grades `100`, `90` and `80`, the efficiency work is `optimize`. At a lower grade it is `report only`, and the work goes to success first.

### The 80% rule

A job holds 80% when, at 3 daily checks in a row, its 7-day ratio is 0.80 or more and it has 30 attempts or more in the 7 days. Only then does the owner tune the caps of the job from its real performance. Under 30 attempts, the ratio is too few to judge, and the job does not hold 80%.

A job that holds 80% keeps it until the evidence is clear that it fell. At each daily check, compute the Wilson upper bound of the 7-day ratio with z = 1.96 (95%), for `s` successes in `n` attempts and `p = s / n`:

```text
upper = (p + z²/(2n) + z·√(p(1 − p)/n + z²/(4n²))) / (1 + z²/n)
```

When the upper bound is under 0.80, the job no longer holds 80%. For example, 20 successes in 30 attempts give an upper bound of 0.81, and the job keeps the hold. 18 successes in 30 attempts give 0.75, and the hold ends.

## Specs

- `openspec/specs/roadmap-service-logs/spec.md`, requirement "Each roadmap job logs one result line for each attempt".
- `openspec/specs/roadmap-job-grades/spec.md`, the job grade of each workflow and the report of `devops roadmap eval grades`.
