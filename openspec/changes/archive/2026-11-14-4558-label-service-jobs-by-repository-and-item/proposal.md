# Proposal: #4558 feat(roadmap): label Service Jobs by repository and item

## Why
A runner Job carries only the hashed label `implement-repo` and the generic name `devops-cli-job`. A person cannot list the Jobs of one repository or one item with `kubectl`. Loki cannot label the log stream of a Job pod by repository. The new labels must land before the Service and the Workflows rely on them, because a later rename of the selector key has no safe rollout. Closes #4558.

## What Changes
- `src/devops_cli/k8s/cluster_job.py`: Update `build_job` to apply repository labels (`roadmap.devops-cli/owner`, `roadmap.devops-cli/repo`, `roadmap.devops-cli/item`), standard labels (`app.kubernetes.io/component`, `app.kubernetes.io/part-of: devops-cli-stack`, `app.kubernetes.io/managed-by: devops-cli`), and the annotation `roadmap.devops-cli/repository` on both the Job and the pod template.
- Implement `runner_job_name` and `runner_job_labels` helper functions.
- Update `src/devops_cli/roadmap/implement/implement_submit.py` to name runner Jobs `devops-cli-implement-<slug>-<item>-<6 hex>` and pass repository and item metadata to `build_job`.
- Update `src/devops_cli/commands/k8s/cluster_jobs.py` to name runner jobs with `adhoc_name` and include repository labels on runner jobs and dry run output.
- Update `k8s/devops/cronjob-runner.yaml` to set `OTEL_SERVICE_NAME: roadmap-implement`.
- Update dashboard descriptions in `k8s/devops/dashboards/ai-spend.json` and `k8s/devops/dashboards/devops-cli.json` to reference `roadmap-implement`.

## Capabilities
- `roadmap-implement-runner`: repository and item labels, annotations, runner Job naming, and telemetry service name.

## Impact
- Jobs and pods can be queried by repository and item via `kubectl -l roadmap.devops-cli/repo=...,roadmap.devops-cli/item=...`.
- Loki can index logs by repository annotation.
- Backwards compatibility is preserved by keeping `implement-repo` and `app.kubernetes.io/name: devops-cli-job`.

## Feasibility
- Verified `RepoRef` has `adhoc_name`, `owner_label`, `repo_label`, and `key`.
- Verified `build_job` callers and tests can be updated cleanly.

## Existing Tool Considered
Kubernetes standard labels and annotations and kube-state-metrics cover the need. No external build needed.
