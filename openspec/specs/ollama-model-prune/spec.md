# ollama-model-prune Specification

## Purpose
The removal of the Ollama models that no tier of a node serves, so that the root disk of the node stays below the threshold where the kubelet deletes images.

## Requirements

### Requirement: The prune keeps the models that the tiers of a node serve
The prune SHALL remove only a model that no tier with a pod on the node serves, where the models of each tier are those that the gateway config sends to it.

#### Scenario: One extra model on a node with two tiers
- **WHEN** A node runs the tiers `ollama-16gib` and `ollama-24gib-embed-gpu0`, and its model store holds a Gemma model that neither tier serves
- **THEN** The plan names the Gemma model for that node and names no other model.

#### Scenario: A model that a tier serves stays
- **WHEN** A node runs `ollama-48gib-fast` and its store holds `qwen3.8:27b`
- **THEN** The plan removes no model on that node.

### Requirement: The plan names each node and each model once
The plan SHALL name each model to remove once for each node, also when two tiers of the node serve the same model.

#### Scenario: A model that two tiers of one node serve
- **WHEN** The tiers `ollama-48gib-fast` and `ollama-64gib-standard` run on one node and both serve `qwen3.8:27b`
- **THEN** The keep set of the node holds one `qwen3.8:27b`, and the plan names the node once.

#### Scenario: A plan that a person reads
- **WHEN** A person runs `devops k8s ollama prune --plan`
- **THEN** The output names each node and each model it would remove, and it removes no model.

### Requirement: A dry run of the prune makes no request
A dry run MUST make no request to the cluster and MUST print each `kubectl exec` and `ollama rm` command that it would run.

#### Scenario: Dry run of the prune
- **WHEN** A person runs `devops k8s ollama prune --dry-run`
- **THEN** The output holds the `kubectl exec` command of each gateway target tier, and no request leaves the workstation.

### Requirement: The written keep set matches the gateway config
The GPU Placement section of `k8s/README.md` MUST name each model that each serving tier keeps, and a test MUST fail when a name differs from the gateway config.

#### Scenario: A model added to the gateway config
- **WHEN** The gateway config names a model that the table of `k8s/README.md` does not
- **THEN** `tests/k8s/test_k8s_ollama_models.py` fails and names the model and the tier.

### Requirement: An unreadable model list stops the node
The prune MUST remove no model on a node whose `ollama list` fails, and MUST name that node.

#### Scenario: `ollama list` fails on one node
- **WHEN** The `ollama list` of a node exits non-zero
- **THEN** The command removes no model on that node, names the node, and exits non-zero.
