# Proposal: #4845

## Why

The owner tunes the caps of a roadmap job only after the job holds 80% success, so each job needs an exact count of its attempts and of its intended results. No counter gave it when the issue was filed: `increase(devops_cli_roadmap_stage_total{result="staged"}[7d])` was 0 against about 39 staged items, because a new series lost its first count (#4684), and the implement counters disagreed (#4703). Both are fixed now, but the counters still give no common ratio: each job counts other results, the refine judge counts no approval, and the alternatives check counts no refused reply. The 80% check also needs the counts of each attempt, which a metric label cannot hold for each item. Closes #4845.

## What Changes

- The new module `src/devops_cli/roadmap/job_result.py` writes one `roadmap job result:` line for each attempt of a job. The line holds the job, the repository, the item, the result, `success`, the failure class, `infra`, the counts of the job and the devops-cli version. It holds no text of an issue or of a model. The module holds the intended results of each job and the failure classes that a cut of the infrastructure gives.
- `stage`: `emit_stage_results` logs each item that the round tried, with its plan runs, gate returns, review runs, tokens and seconds. The planner keeps these counts for each item.
- `implement`: `_report` logs each runner Job that ended, with the result that its runner recorded, its repair rounds, tokens and seconds. `ClusterJob` reads the time of the end condition of a Job.
- `refine`: `RefineWriter.settle` logs the next step of each item, or `error` with the class of a failed model call or write.
- `refine_judge`: `judge` logs each review that calls the model, with its verdict and its open findings. It gets the repository.
- `alternatives`: `AlternativesWriter.settle` logs each written check and each failure, with its searches and its reason code. The writer gets the repository, and a failed model call keeps its failure class.
- `intake`: `apply_intake` logs each candidate that it counts.
- The dashboard `devops-cli Telemetry` gets the row `Roadmap Job Success`, with Loki `count_over_time` panels.
- `docs/roadmap/job-success.md` gives the line, the intended result of each job, the query and the 80% rule.

## Capabilities

- `roadmap-service-logs`: ADDED requirement "Each roadmap job logs one result line for each attempt".

## Impact

- `src/devops_cli/roadmap/job_result.py` (new), `stage/stage.py`, `implement/implement_submit.py`, `refine/refine.py`, `refine/refine_judge.py`, `alternatives.py`, `intake/intake.py`, `run.py`, `commands/roadmap.py` and `k8s/cluster_job_api.py`.
- `k8s/monitoring/dashboards/devops-cli.json` and `docs/roadmap/job-success.md`.
- Each attempt adds one INFO line to the Service log. No metric, setting or ConfigMap changes.
- The change fits one pull request.

## Feasibility

Confirmed on origin/main 6cc475b5a and on the live Loki:

- The Service writes JSON lines with the key `message` to the stream `{namespace="devops", app_kubernetes_io_name="roadmap-service"}`. The query `| json message | line_format "{{.message}}" | regexp ...` reads the existing `stage left out:` and `stage review round:` lines by label, so the same form reads the new line.
- #4684 and #4703 are fixed (releases 0.116.1 and 0.116.0). The refine judge and the alternatives check still count no approval and no refused reply, so the premise holds.
- Loki keeps logs 30 days (`k8s/logging/loki-values.yaml`), so a 7-day window and 3 daily checks fit.
- The stream has the label `job`, so the query names the extracted label `roadmap_job`.
- `_Planner` of `stage.py` clears its traces for each item, so the traces after `plan` are the runs of that item.
- The runner records `implement.result` (`ImplementResult`), and the Service clears it when it makes a Job.

The cap extensions and the implement halt turns have no count in the code yet. The changes that add a cap extension add the count `extensions` to the line.

## Existing Tool Considered

Loki `count_over_time` and Grafana panels on the existing log pipeline cover the count and the dashboard; the change adds no store and no tool. Prometheus recording rules can give the same ratio later, now that #4684 and #4703 are fixed. Cost to build: about 1M tokens and 1 day; to keep: one line in each job.
