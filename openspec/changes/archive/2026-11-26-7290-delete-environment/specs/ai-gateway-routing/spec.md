## ADDED Requirements

### Requirement: The render follows the thresholds of the environment tree
`devops ai gateway render` SHALL read `embedding_only` and `per_gpu` from `llm/profiles/gpu-thresholds.yaml` of the environment tree, each a value of `nvidia.com/gpu.architecture`. A tier template SHALL be at or below a threshold when the newest architecture that it accepts is that architecture or an older one. A tier newer than both thresholds SHALL run as its template says, with no embedding deployment.

#### Scenario: A tier newer than both thresholds
- **WHEN** a tier that accepts `pascal` is rendered with the thresholds `maxwell` and `kepler`
- **THEN** its DaemonSet equals its template, and it has no embedding deployment

#### Scenario: An unknown architecture
- **WHEN** a threshold names an architecture that the label does not have
- **THEN** the load fails and names the value

### Requirement: A render writes only the rendered regions
`devops ai gateway render` SHALL write only the regions between the `rendered` lines of the profiles, the services and the gateway config of the tree. Without `--apply`, it SHALL show the diff and write no file.

#### Scenario: A second render
- **WHEN** the output of a render is rendered again with the same inputs
- **THEN** the output does not change

#### Scenario: A lower threshold
- **WHEN** an output of a higher threshold is rendered with a lower one
- **THEN** the output equals a render of the lower threshold from empty regions

## MODIFIED Requirements

### Requirement: A gateway attempt ends before the deadline of the call
The default of `ai.request_timeout_seconds` SHALL be less than `CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS` and the `activeDeadlineSeconds` of `k8s/devops/cronjob-runner.yaml`. The gateway config of the environment tree sets the router timeout, which has to be less than the call deadlines.

#### Scenario: The timeouts nest
- **WHEN** a person runs `kubectl -n llm get configmap -l app.kubernetes.io/name=llm-gateway -o yaml` and `kubectl -n devops get cronjob devops-cli-runner -o yaml` on the cluster
- **THEN** the router timeout and each deployment timeout of the gateway config are less than each default call deadline, and the default of `ai.request_timeout_seconds` is less than the stage margin and the `activeDeadlineSeconds` of the runner CronJob

## REMOVED Requirements

### Requirement: Every gateway route names a model that its tier serves
**Reason**: It compares product code with a gateway config, a tier manifest or a values file that devops-cli no longer holds (#7290).
**Migration**: The environment repository can compare its files with the defaults of the CLI.

### Requirement: The default fallback model is a model that the default Ollama tier serves
**Reason**: It compares product code with a gateway config, a tier manifest or a values file that devops-cli no longer holds (#7290).
**Migration**: The environment repository can compare its files with the defaults of the CLI.

### Requirement: Each Open WebUI default model is a group that the gateway serves
**Reason**: It compares product code with a gateway config, a tier manifest or a values file that devops-cli no longer holds (#7290).
**Migration**: The environment repository can compare its files with the defaults of the CLI.

### Requirement: Each default model of the CLI is a model that the default Ollama tier and the gateway serve
**Reason**: It compares product code with a gateway config, a tier manifest or a values file that devops-cli no longer holds (#7290).
**Migration**: The environment repository can compare its files with the defaults of the CLI.

### Requirement: Each virtual model of the GPU matrix is a group that the gateway serves
**Reason**: It compares product code with a gateway config, a tier manifest or a values file that devops-cli no longer holds (#7290).
**Migration**: The environment repository can compare its files with the defaults of the CLI.

### Requirement: Gateway virtual models and default routes match served config groups
**Reason**: It compares product code with a gateway config, a tier manifest or a values file that devops-cli no longer holds (#7290).
**Migration**: The environment repository can compare its files with the defaults of the CLI.

### Requirement: Guard against a one-model tier
**Reason**: It compares product code with a gateway config, a tier manifest or a values file that devops-cli no longer holds (#7290).
**Migration**: The environment repository can compare its files with the defaults of the CLI.

### Requirement: The gateway routes embeddings with simple-shuffle across order 1 tiers
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The gateway routes qwen3.8:27b and devops-chat only to 48gib and 64gib tiers
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Gateway routes devops-triage to the standard tier
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Gateway fallbacks include triage and background targets
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Each chat deployment of the gateway declares the window of its tier
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The gateway has no context-window fallback
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Every Ollama tier sets one KV cache type
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Hosted groups call a provider with an optional key
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: A Claude group sets its prices and drops refused parameters
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The gateway reaches providers on port 443 only
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Hosted groups join no pool
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The 48 GiB and 64 GiB tiers load one model for good
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The gateway sends the 48 GiB and 64 GiB tiers one model
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The dated DeepSeek group falls back to the undated model with the same provider filter
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: A Claude group caches its prompt prefix
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The gateway router maps local and provider model aliases
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Health checks cover only the hosted DeepSeek groups
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The router counts failures below the LiteLLM default
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The gateway sends the 16 GiB tier nothing
**Reason**: `k8s/README.md` of devops-cli describes the product base and the commands only (#7290).
**Migration**: The README of the environment repository describes its own services.

### Requirement: One documented call for each hosted group
**Reason**: `k8s/README.md` of devops-cli describes the product base and the commands only (#7290).
**Migration**: The README of the environment repository describes its own services.

### Requirement: Each call sends only the gateway key
**Reason**: `k8s/README.md` of devops-cli describes the product base and the commands only (#7290).
**Migration**: The README of the environment repository describes its own services.

### Requirement: A documented structured call
**Reason**: `k8s/README.md` of devops-cli describes the product base and the commands only (#7290).
**Migration**: The README of the environment repository describes its own services.

### Requirement: The documented run and its record
**Reason**: `k8s/README.md` of devops-cli describes the product base and the commands only (#7290).
**Migration**: The README of the environment repository describes its own services.

### Requirement: GPU architecture thresholds set the tiers of old GPUs
**Reason**: devops-cli tracks no thresholds file and no tier manifest (#7290).
**Migration**: See `The render follows the thresholds of the environment tree` and `A render writes only the rendered regions`.

### Requirement: The tracked manifests are the output of the render
**Reason**: devops-cli tracks no thresholds file and no tier manifest (#7290).
**Migration**: See `The render follows the thresholds of the environment tree` and `A render writes only the rendered regions`.
