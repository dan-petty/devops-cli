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

### Requirement: deploy-stack renders the credential-free sandbox ConfigMap
The command `devops k8s deploy-stack --stack devops` SHALL render and apply ConfigMap `devops-cli-config-sandbox` in namespace `devops` from the active config, on the native manifest path and on the Argo CD-managed path, and SHALL apply `devops-cli-config` first.

#### Scenario: Deploy the devops stack on a native cluster
- **WHEN** deploy-stack runs for the devops stack on a native cluster
- **THEN** the command sends a manifest on stdin whose metadata.name is devops-cli-config-sandbox and whose metadata.namespace is devops, after the manifest of devops-cli-config

#### Scenario: Deploy the devops stack on an Argo CD-managed cluster
- **WHEN** deploy-stack runs for the devops stack on a cluster that Argo CD manages
- **THEN** the command applies devops-cli-config-sandbox from the active config before it leaves the manifests to Argo CD

### Requirement: The sandbox ConfigMap drops every credential key at any depth
The rendered `devops-cli-config-sandbox` SHALL omit every key of its `devops-cli.yaml` value whose lower-case name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS` and whose value is not a number or a boolean, at any depth of maps and lists, and SHALL keep every other key with its value.

#### Scenario: Credential keys at the top level and nested
- **WHEN** the template config holds github_token, api_key, db_password and a secret key beside non-credential keys
- **THEN** the rendered devops-cli.yaml value holds none of those four keys and still holds the non-credential keys with their values

### Requirement: The sandbox ConfigMap keeps a number under a credential-like name
The rendered `devops-cli-config-sandbox` MUST keep a key whose name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS` when its value is a number or a boolean, because such a value is a count and not a credential.

#### Scenario: Token budgets of the template
- **WHEN** the sandbox ConfigMap is rendered from the template k8s/devops/configmap.example.yaml
- **THEN** roadmap.stage.step_tokens, roadmap.review.token_budget, roadmap.implement.step_token_budget and roadmap.implement.item_token_budget keep their template values

### Requirement: The sandbox ConfigMap keeps the name and the data key the run Job mounts
The rendered ConfigMap MUST keep the name `devops-cli-config-sandbox` and the single data key `devops-cli.yaml`, so the planner run Job mounts it at `/config` with `DEVOPS_CLI_CONFIG` unchanged.

#### Scenario: Name and data key are stable
- **WHEN** the sandbox ConfigMap is rendered from any config
- **THEN** metadata.name is devops-cli-config-sandbox and data holds exactly the key devops-cli.yaml

### Requirement: teardown-stack deletes the sandbox ConfigMap
The command `devops k8s teardown-stack --stack devops` SHALL delete ConfigMap `devops-cli-config-sandbox` with `--ignore-not-found`, as it deletes `devops-cli-config`.

#### Scenario: Tear down the devops stack
- **WHEN** the teardown runs for the devops stack
- **THEN** the command issues kubectl delete configmap devops-cli-config-sandbox -n devops --ignore-not-found and exits 0 when the ConfigMap is absent

### Requirement: A dry run names the sandbox ConfigMap and prints no value of it
The commands `devops k8s deploy-stack --stack devops --dry-run` and `devops k8s teardown-stack --stack devops --dry-run` SHALL name the sandbox ConfigMap with the other rendered resources and SHALL print no value of it.

#### Scenario: Dry run of the devops stack
- **WHEN** the command runs with --dry-run for the devops stack
- **THEN** the details name devops/devops-cli-config-sandbox and hold none of its content

### Requirement: A test names each credential key of the rendered config
A test SHALL parse the rendered ConfigMap, walk every key of the `devops-cli.yaml` value at any depth, and name each key whose lower-case name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS` and whose value is not a number or a boolean.

#### Scenario: The walk names a credential key
- **WHEN** the walk runs on a hand-built config that holds github_token at the top level and ai.api_key nested
- **THEN** it names github_token and ai.api_key

#### Scenario: The rendered ConfigMap holds no credential key
- **WHEN** the walk runs on devops-cli-config-sandbox rendered from a template that holds a credential key at the top level and one nested
- **THEN** it names no key
