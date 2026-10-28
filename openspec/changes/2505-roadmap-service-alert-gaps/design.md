# Design

## The count of the last hour

Each count rule reads its counter `x` as:

```promql
(last_over_time(x[1h]) unless last_over_time(x[1h] offset 1h)) or increase(x[1h])
```

- **A new series.** A series with no sample in the hour before the range started in the range. On the OTLP path the collector starts a stream again from zero after an hour with no sample (`max_stale: 1h`), and on the scrape path a counter of a new pod or label set starts at its first count. So the last value of the series is all of its count, and it is exact: `increase()` would extrapolate to the start of the range.
- **Any other series.** `increase()` counts it, as before. It reads only the samples in the range, so a series from before the hour adds none of its earlier count.
- **One sample.** A new series with one sample gives its value. An old series with one sample in the range gives nothing, as `increase()` does.

The three rules sum this count: by repository and lane for the failed jobs, over all series for the requests.

## The job start of a new pod

`RepoWorker.start` sets the job start gauge of its lane to the time of its clock, before its thread starts. The first job sets the gauge again, as before. So a lane of a new pod has a series from the start, and `time() - max by (repo, lane) (...)` grows until the lane starts a job. The series of the old pod goes stale, and `max by (repo, lane)` reads the series of the new pod.

## Rejected alternatives

- **The #2472 correction, `increase(x[1h]) + (x offset 1h * 0 or min_over_time(x[1h]))`, also on the request rules.** Rejected: the instant selector at `offset 1h` looks back 5 minutes only. A series with no sample in those 5 minutes counts as new, and the rule adds all of its count. In the promtool case of an error series with samples 5, 6 and 7, it gives 8 for 2 failed jobs, and a GitHub request series at 2000 would give more than 2000. It also gives no result for a new series with one sample, because `increase()` needs two.
- **`increase(x[1h]) + min_over_time(x[1h])` for a new series.** Rejected: `increase()` extrapolates the series to the start of the range, so the sum counts about one interval twice. For the stream of 300 and 20 more every 5 minutes, it gives 540, not 520.
- **A zero sample at the start of each series (created timestamps).** Rejected for this change: the Prometheus server and the collector have the settings of #2039, but series that started on 2026-10-28 have no zero sample, and Prometheus has no `_created` series. The collector sends remote write 1.0, which has no field for a created timestamp. #2506 fixes the path. When it is fixed, plain `increase()` is enough, and the rules can go back to it.
- **`max_over_time(devops_cli_service_job_start_timestamp_seconds[1d])` in `RoadmapServiceLaneStalled`.** Rejected: it keeps the series of the old pod for one day, so a lane of a repository that was removed from `service.repos` fires for a day. It stops after the day, and it never sees a lane that started no job on any pod.
- **A gauge at 0 before the first job.** Rejected: `time() - 0` is more than 2 hours at once, so the rule fires 10 minutes after each start when a pause or the request budget holds the first rounds, and the summary gives a duration from 1970.
- **A second gauge for the start of the worker.** Rejected: it adds a series for each lane and an `or` in the rule, and the rule asks one question: how long the lane waited for a job to start.

## Limits

- A new series whose counter goes back to zero in its first hour, such as at a restart of the container in the same pod, counts only its value after the reset. `RoadmapServiceRestarted` fires for the restart.
- A stream that starts again after more than one hour with no sample, where that last old sample is in the hour before the range, counts with `increase()` until that sample is more than one hour before the range. The rule then counts its first value.
- A scraped series with no sample for an hour, for example when the scrape stops, counts as new when the scrape starts again.

## Tests

- `test_the_roadmap_service_rules_watch_identity_jobs_lanes_pods_and_request_volume` pins the three expressions with the helper `_hour_count`.
- `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` adds the promtool cases: a sparse error series from before the hour stays quiet, a new error series with one sample of 3 fires, a GitHub and a model request stream that start in the hour fire with their exact counts, a sparse GitHub request stream at 2000 stays quiet, and a lane of a new pod fires 2 hours after its worker started.
- `test_a_worker_sets_its_lanes_job_start_to_its_own_start_before_its_first_job` checks the gauge after a worker starts and before its first job.
