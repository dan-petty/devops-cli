# k8s-planner-run-job Specification

## Purpose
The manifest, the NetworkPolicy, the Role row and the admission rules of the planner's sandboxed run Job (ADR 0018): one read-only command in a pod with no credential, no token, no network and no writable path but two small volumes.

## Requirements

### Requirement: A suspended CronJob holds the planner run pod
The devops stack SHALL hold the suspended CronJob `devops-cli-planner-run` with the pod of the planner run Job.

#### Scenario: The CronJob is read from the stack
- **WHEN** a test renders `k8s/devops/roadmap-service/`
- **THEN** the CronJob sets `suspend: true`, `backoffLimit: 0`, `restartPolicy: Never`, `activeDeadlineSeconds: 120` and `ttlSecondsAfterFinished`

### Requirement: The pod holds two writable volumes and two read-only ones
The pod SHALL mount `emptyDir` `home` at `/home/devops` and `emptyDir` `tmp` at `/tmp`, each with a size limit. It SHALL mount ConfigMap `devops-cli-config-sandbox` at `/config` read only and claim `roadmap-service-home` at `/repo` read only, and it SHALL hold no other volume.

#### Scenario: A writable path outside the two volumes
- **WHEN** a Job of the template adds an `emptyDir` volume, or sets `readOnly: false` on the claim
- **THEN** the admission policy refuses the Job

### Requirement: The pod holds no credential and no token
The pod SHALL set `automountServiceAccountToken: false`, and its container SHALL hold no `envFrom` and no `valueFrom`.

#### Scenario: A Secret in envFrom
- **WHEN** a Job of the template sets `envFrom` with Secret `devops-cli`
- **THEN** the admission policy refuses the Job

### Requirement: The pod runs as UID 1000 with no privilege
The pod SHALL set `runAsNonRoot: true`, `runAsUser: 1000`, `runAsGroup: 1000` and `seccompProfile: RuntimeDefault`, and the container SHALL set `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` and drop every capability.

#### Scenario: The security context of the pod and of the container
- **WHEN** a test renders the Job from the template
- **THEN** the pod and the container hold each field of the security context

### Requirement: The run Job caps CPU and memory
The container SHALL request and limit 1 CPU and 2Gi of memory, and the Job SHALL set a deadline of 120 seconds.

#### Scenario: The resources and the deadline
- **WHEN** a test renders the Job from the template
- **THEN** both the request and the limit are 1 CPU and 2Gi, and the deadline is 120

### Requirement: The Role allows get on the CronJob
Role `roadmap-service-jobs` SHALL allow `get` on CronJob `devops-cli-planner-run`.

#### Scenario: The rules of the Role
- **WHEN** a person runs `kubectl auth can-i get cronjob/devops-cli-planner-run -n devops --as=system:serviceaccount:devops:roadmap-service`
- **THEN** the API server answers `yes`

### Requirement: The admission policy admits the planner shape
The ValidatingAdmissionPolicy `roadmap-service-jobs` SHALL admit the Job that `PLANNER_TEMPLATE` renders, and SHALL refuse a Job that breaks a control.

#### Scenario: The Job of the template passes
- **WHEN** a test runs the policy against the rendered Job
- **THEN** the policy holds no refusal

### Requirement: The kustomization and deploy-stack hold the new files
The kustomization of the roadmap Service and `deploy-stack` SHALL list the CronJob and the NetworkPolicy.

#### Scenario: A read of the kustomization
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/devops`
- **THEN** the render holds CronJob `devops-cli-planner-run` and its NetworkPolicy, and the row passes only when `deploy-stack` or an owned exemption applies every NetworkPolicy under `k8s/`
