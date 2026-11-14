# Design

## Decisions

### 1. Label and annotation values
`build_job` sets `roadmap.devops-cli/owner` to the casefolded owner, `roadmap.devops-cli/repo` to the casefolded repository name, and `roadmap.devops-cli/item` to the issue number. The annotation `roadmap.devops-cli/repository` holds the casefolded `owner/name`. Both the Job metadata and the pod template metadata receive these labels and the annotation.

### 2. Standard labels
`build_job` sets `app.kubernetes.io/component: roadmap-<row>`, `app.kubernetes.io/part-of: devops-cli-stack` and `app.kubernetes.io/managed-by: devops-cli`. The label `app.kubernetes.io/name: devops-cli-job` stays so network policies and admission policies continue to admit the pod.

### 3. Backward compatibility
The legacy label `implement-repo` with its hash digest value stays on runner Jobs so that the Service continues to detect Jobs created by earlier versions.

### 4. Runner Job naming
The runner Job receives the ad hoc name `devops-cli-implement-<slug>-<item>-<6 hex>` from `RepoRef.adhoc_name`. The name length is bounded to 63 characters or fewer.

### 5. Telemetry service name
The runner CronJob manifest sets `OTEL_SERVICE_NAME: roadmap-implement`. Mentions of `devops-cli-job` in dashboard descriptions are updated to include `roadmap-implement`.

## Rejected Alternatives

- Using full `owner/name` in label: Rejected because `/` is not permitted in Kubernetes label values.
- Applying annotation to Job metadata only: Rejected because Loki requires the annotation on the pod template to label log streams.
- Dropping `implement-repo` immediately: Rejected because a rolling Service would fail to see running Jobs started by previous releases.
