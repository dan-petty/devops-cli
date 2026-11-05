## ADDED Requirements

### Requirement: The 48 GiB and 64 GiB tiers load one model for good
The DaemonSets `ollama-48gib` and `ollama-64gib` SHALL set `OLLAMA_CONTEXT_LENGTH` to 262144, the native context length of `qwen3.8:27b`, `OLLAMA_NUM_PARALLEL` to 1, `OLLAMA_MAX_LOADED_MODELS` to 1 and `OLLAMA_KEEP_ALIVE` to `-1`.

#### Scenario: The settings of the two tiers
- **WHEN** the profiles are read
- **THEN** both tiers set the four values above

### Requirement: The gateway sends the 48 GiB and 64 GiB tiers one model
Every gateway deployment that calls a Service which selects `ollama-48gib` or `ollama-64gib` SHALL name `ollama_chat/qwen3.8:27b`. No embedding deployment SHALL call either tier. A tier rendered from a template above the `embedding_only` threshold SHALL get no embedding deployment, and the 48 GiB template SHALL keep one model loaded.

#### Scenario: A second model on a tier
- **WHEN** a gateway deployment sends `qwen3-coder:30b`, `gemma4:31b` or an embedding model to `ollama-48gib-fast` or `ollama-64gib-standard`
- **THEN** the check that reads the gateway config fails

#### Scenario: A chat tier from a template
- **WHEN** a tier template is rendered above the `embedding_only` threshold
- **THEN** the render writes no embedding deployment for it

#### Scenario: Embeddings keep their tiers
- **WHEN** the gateway config is loaded
- **THEN** `qwen3-embedding:0.6b` has deployments on `ollama-24gib-embed-gpu0` and `-gpu1` at order 1 and on `ollama-16gib-fast` at order 2, and on no other tier

## MODIFIED Requirements

### Requirement: Each Open WebUI default model is a group that the gateway serves
Each model that the `DEFAULT_MODELS` of the Open WebUI values names SHALL be a model group of the gateway config with a deployment on a serving tier. The Open WebUI values SHALL NOT set `MODEL_FILTER_LIST`, which Open WebUI does not read.

#### Scenario: The Open WebUI values
- **WHEN** the Open WebUI values are read
- **THEN** each model of `DEFAULT_MODELS` is a gateway group with a deployment on a serving tier, and the values set no `MODEL_FILTER_LIST`

#### Scenario: A model that the gateway does not serve
- **WHEN** the check reads `qwen2.5-coder:7b`, `devops-flagship` or an Ollama model name that is no group
- **THEN** it names each of them, and it passes `devops-chat` and `qwen3.8:27b`

### Requirement: Each default model of the CLI is a model that the default Ollama tier and the gateway serve
The default of `ai.model`, each chat model of `devops ai bundle-models`, and the model that a task benchmark runs when it gets no candidate SHALL be a model that a deployment of the gateway config sends to a serving tier that the default Ollama Service selects. Each SHALL also be a model group of the gateway config with a deployment on a serving tier.

#### Scenario: The defaults with no configuration
- **WHEN** the CLI runs with no `ai.model` set, `devops ai bundle-models` runs, and a task benchmark gets no candidate
- **THEN** each names a model that the gateway config sends to a serving tier of the default Ollama Service, and a gateway group with a deployment on a serving tier

#### Scenario: The embedding model
- **WHEN** `devops ai bundle-models` lists the default embedding model
- **THEN** a deployment of the gateway config sends it to a serving tier that the default embedding Service selects, and not to the tier of the default Ollama Service

#### Scenario: The benchmark with no candidate
- **WHEN** a task benchmark gets an empty list of candidates
- **THEN** it runs the configured `ai.model`

### Requirement: Each virtual model of the GPU matrix is a group that the gateway serves
The virtual model of each hardware profile and of each Service alias that `devops k8s gpu-matrix` shows SHALL be a model group of the gateway config with a deployment on a serving tier.

#### Scenario: The GPU matrix
- **WHEN** `devops k8s gpu-matrix` reads its profiles and Service aliases
- **THEN** each virtual model is a gateway group with a deployment on a serving tier, and a 70B profile names `devops-reasoning`

### Requirement: GPU architecture thresholds set the tiers of old GPUs
`k8s/llm/profiles/gpu-thresholds.yaml` SHALL hold `embedding_only` and `per_gpu`, both `pascal`, each a value of `nvidia.com/gpu.architecture`. A tier in `k8s/llm/profiles/tier-templates/` SHALL be at or below a threshold when the newest architecture that it accepts is that architecture or an older one. A tier newer than both thresholds SHALL run as its template says.

#### Scenario: The tracked values
- **WHEN** the thresholds file is loaded
- **THEN** both values are `pascal`

#### Scenario: A tier newer than both thresholds
- **WHEN** a tier that accepts `pascal` is rendered with the thresholds `maxwell` and `kepler`
- **THEN** its DaemonSet equals its template, and it has no embedding deployment

#### Scenario: An unknown architecture
- **WHEN** a threshold names an architecture that the label does not have
- **THEN** the load fails and names the value

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
- **THEN** each instance keeps the chat settings of the template, and none has an embedding deployment
