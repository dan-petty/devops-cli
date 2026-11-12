# The success of the roadmap jobs

The owner tunes the caps and the limits of a roadmap job only after the job holds 80% success. This page gives the measure of each job, the log line that counts it, the query that reads it and the 80% rule. The rules that a test checks are in the spec named at the end of this page.

## Why a log line and not a counter

The counters of the jobs give no common ratio. Each job counts other results, the review of refine counts no approval, and the alternatives check counts no refused reply. Before release 0.116.1, a new series of a counter also lost its first count (#4684). A log line holds the counts of each attempt, such as its tokens and its gate returns, which a metric label cannot hold for each item. So each job writes one log line for each attempt, and Loki counts the lines. Prometheus recording rules can give the same ratio later.

## The result line

The roadmap Service writes one line for each attempt of a job:

```text
roadmap job result: job=<job> repo=<owner/repo> item=#<n> result=<result> success=<true|false> class=<class> infra=<true|false> <count>=<n> ... version=<version>
```

- `job` is `stage`, `implement`, `refine`, `refine_judge`, `alternatives` or `intake`.
- `success` is `true` when the result is the intended result of the job (table below).
- `class` is the failure class of `roadmap/failure.py`, or `none`.
- `infra` is `true` for a class that a cut of the infrastructure gives: `provider`, `ci_infra`, `oom` and `limit_reached`. The ratio counts these attempts as failures, and the dashboard shows their share apart.
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

A `stage` item that is staged with an open finding of the review is `failed` with the class `plan_defect`. An `implement` Job that recorded no result, such as a pod that the kernel killed, is `stopped`. Its `seconds` run from the start of its pod to its end, and are 0 when the Job is gone.

Some attempts write no line:

- A stop of the Service ends the round, and the attempt in progress writes no line.
- An alternatives check whose body a person changed since the read writes no line. The next round checks the item again.

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
sum by (roadmap_job) (count_over_time(<base> | success="true" [7d]))
  / sum by (roadmap_job) (count_over_time(<base> [7d]))
```

## The 80% rule

A job holds 80% when, at 3 daily checks in a row, its 7-day ratio is 0.80 or more and it has 30 attempts or more in the 7 days. Only then does the owner tune the caps of the job from its real performance. Under 30 attempts, the ratio is too few to judge, and the job does not hold 80%.

A job that holds 80% keeps it until the evidence is clear that it fell. At each daily check, compute the Wilson upper bound of the 7-day ratio with z = 1.96 (95%), for `s` successes in `n` attempts and `p = s / n`:

```text
upper = (p + z²/(2n) + z·√(p(1 − p)/n + z²/(4n²))) / (1 + z²/n)
```

When the upper bound is under 0.80, the job no longer holds 80%. For example, 20 successes in 30 attempts give an upper bound of 0.81, and the job keeps the hold. 18 successes in 30 attempts give 0.75, and the hold ends.

## Spec

`openspec/specs/roadmap-service-logs/spec.md`, requirement "Each roadmap job logs one result line for each attempt".
