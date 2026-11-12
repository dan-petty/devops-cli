# Design

## Decisions

- **The outcome comes from the failure class.** `_outcome(state, failure)` gives `failed` when the report finds a failure class, else the state of the Job. The report already finds the class once for the comment, the record and the failures counter, so the two counters read the same fact. Then `sum(failures) <= jobs{result="failed"}` is true for each window. A Job that the controller marked Failed with no failure class (for example, an item that a person claimed) stays `failed`.
- **The record keeps the state of the Job.** `implement.job_state` and the attempt log line keep the Kubernetes state, because the stop logic and the digest rules read it. Only the counter label changes.
- **A closed item is reported only while the cluster holds its Job.** The runner Jobs have `ttlSecondsAfterFinished: 86400` (`k8s/devops/cronjob-runner.yaml`), and the row runs every 7 minutes, so each Job of a closed item is seen before the controller deletes it. A record whose Job is gone cannot be told apart from a record of an earlier version, so it is not reported.
- **A closed item is no stop.** Nothing creates a Job for a closed item, so a stop of it has no use, and a Blocked Status on a closed issue would be wrong.
- **The check of the repository is at the start of the round.** `run_implement_round` is the one entry of the row. A refusal there writes nothing and makes no request, and the round fails, so the row error counter and the Service log show the cause.

## Rejected alternatives

- **One counter of attempts with the labels `result` and `class`.** The issue proposed it. The jobs counter has the labels `repo` × `item_class` × `result`, which is 7 × 11 × 3 series for each pod. A `class` label multiplies that by the 19 failure classes. Two counters with one shared outcome give the same SLI with less cardinality, and no dashboard or alert rule changes.
- **Report every ended runner Job of the repository from the cluster list, with an annotation as the mark.** In the 7 days to 2026-11-11T14:51:23Z, Loki shows 94 Job creations by the Service and 93 reports, and kube-state-metrics shows 93 runner Jobs that started. So the Service creates the runner Jobs, and the item record is a sufficient source. The annotation adds a second record of the same fact.
- **Refuse an empty label in `GLOBAL_METRICS`.** The registry is generic and does not know which labels a counter needs. The refusal belongs to the code that knows that `repo` is required.
