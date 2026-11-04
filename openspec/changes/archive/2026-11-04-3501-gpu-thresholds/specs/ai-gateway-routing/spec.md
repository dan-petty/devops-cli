## ADDED Requirements

### Requirement: GPU architecture thresholds set the tiers of old GPUs
`k8s/llm/profiles/gpu-thresholds.yaml` SHALL hold `embedding_only` and `per_gpu`, both `pascal`, each a value of `nvidia.com/gpu.architecture`. A tier in `k8s/llm/profiles/tier-templates/` SHALL be at or below a threshold when the newest architecture that it accepts is that architecture or an older one. A tier newer than both thresholds SHALL run as its template says.

#### Scenario: The tracked values
- **WHEN** the thresholds file is loaded
- **THEN** both values are `pascal`

#### Scenario: A tier newer than both thresholds
- **WHEN** a tier that accepts `pascal` is rendered with the thresholds `maxwell` and `kepler`
- **THEN** its DaemonSet equals its template, and its embedding deployment has order 3

#### Scenario: An unknown architecture
- **WHEN** a threshold names an architecture that the label does not have
- **THEN** the load fails and names the value

### Requirement: An embedding-only tier serves embedding models first
A tier at or below `embedding_only` SHALL keep one model loaded, SHALL have the speed tier `embed` and a name with `embed`, and each of its gateway deployments SHALL have order 1. The render SHALL fail and name each group when a generation deployment names such a tier.

#### Scenario: An embedding-only tier
- **WHEN** a tier is rendered at or below `embedding_only`
- **THEN** `OLLAMA_MAX_LOADED_MODELS` is 1, and `OLLAMA_CONTEXT_LENGTH` is the largest RAG chunk, and each embedding deployment has order 1

#### Scenario: A chat route on an embedding-only tier
- **WHEN** a generation deployment names an embedding-only tier
- **THEN** the render fails, names the group and writes no file

### Requirement: A per-GPU tier runs one instance for each GPU
A tier at or below `per_gpu` SHALL render one DaemonSet, one Service and one gateway deployment for each GPU that its template names. Each DaemonSet SHALL claim one `nvidia.com/gpu`, SHALL set `OLLAMA_NOPRUNE`, and SHALL NOT set `OLLAMA_SCHED_SPREAD`. A later instance SHALL require a node with that many GPUs. The name and the VRAM labels of each SHALL give the VRAM of one GPU.

#### Scenario: Two GPUs at both thresholds
- **WHEN** the template of a 48 GiB tier with two GPUs is rendered at both thresholds
- **THEN** the output has `ollama-24gib-embed-gpu0` and `ollama-24gib-embed-gpu1`, and the Service of each selects only its instance

#### Scenario: The second instance
- **WHEN** the second instance is rendered
- **THEN** its node affinity requires an `nvidia.com/gpu.count` of 2 or more, and the first instance has no such requirement

#### Scenario: Each threshold acts alone
- **WHEN** only `per_gpu` includes a tier
- **THEN** each instance keeps the chat settings of the template, and each embedding deployment has order 3

### Requirement: A threshold with no tier to follow it is refused
The render SHALL fail for a threshold newer than the newest architecture of the tier templates.

#### Scenario: A newer threshold
- **WHEN** a threshold is `volta` and the newest architecture of the templates is `pascal`
- **THEN** the render fails and names `volta`

### Requirement: The tracked manifests are the output of the render
The regions between the `rendered` lines of the profiles, the services and the gateway config SHALL equal the output of `devops ai gateway render` for the tracked thresholds and templates. Without `--apply`, the command SHALL show the diff and write no file.

#### Scenario: The tracked files
- **WHEN** the render reads the tracked thresholds, templates and manifests
- **THEN** its output equals the tracked manifests

#### Scenario: A second render
- **WHEN** the output of a render is rendered again with the same inputs
- **THEN** the output does not change

#### Scenario: A lower threshold
- **WHEN** an output of a higher threshold is rendered with a lower one
- **THEN** the output equals a render of the lower threshold from empty regions
