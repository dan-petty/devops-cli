## MODIFIED Requirements

### Requirement: The stage CronJob is the template of a stage Job
The manifests SHALL hold a suspended CronJob `roadmap-stage` in namespace `devops` whose container `stage` runs the runner image `ghcr.io/dan-petty/devops-cli/runner` with ServiceAccount `devops-cli` and no token, takes 2 keys of Secret `devops-cli` and no `envFrom`, gives its pod 120 s after a SIGTERM, and runs its pod again only after exit 75 or a disruption.

#### Scenario: The rendered template
- **WHEN** the gate check renders `k8s/devops` with kustomize.
- **THEN** CronJob `roadmap-stage` names the image `ghcr.io/dan-petty/devops-cli/runner` with no tag, holds the keys `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_AI_API_KEY` through `secretKeyRef` and no MCP token, `terminationGracePeriodSeconds: 120`, 250m CPU and 1Gi requested, 1 CPU and 2Gi as limits, `activeDeadlineSeconds: 10800`, `backoffLimit: 2`, a `podFailurePolicy` that ignores `DisruptionTarget` and fails the Job on each exit code but 75, the telemetry name `roadmap-stage` and the pod labels `app.kubernetes.io/name: devops-cli-job` and `app.kubernetes.io/component: roadmap-stage`.

#### Scenario: The digest of the runner image
- **WHEN** `kubectl kustomize` renders `k8s/overlays/homelab/devops` with the kustomize image entry `ghcr.io/dan-petty/devops-cli/runner`, `newTag: latest` and a digest, as Image Updater writes it into Application `devops`.
- **THEN** the container `stage` of CronJob `roadmap-stage` names that tag and digest, as each container of CronJob `devops-cli-runner` does.
