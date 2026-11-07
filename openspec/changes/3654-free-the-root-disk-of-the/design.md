# Design

## Decisions

- **Remove a model with `ollama rm` in a tier pod of the node.**: Ollama deletes the manifest and the blobs together, so the store stays consistent.
- **Derive the keep set from the gateway routes and the tier pods that run on each node.**: The gateway config is the record of which model each tier is sent, and the pods say which tiers run on the node.
- **Write the keep set in the GPU Placement section of `k8s/README.md` and hold it with `tests/k8s/test_k8s_ollama_models.py`.**: A person reads it where the tiers are described, and the test keeps it equal to the gateway config.
- **Run the prune on demand, after a plan that a person reads.**: A removal is destructive, and the keep set follows the pods that run now, so a person reads the plan first.
- **Keep `LocalPathNodeDiskHigh` at 85%.**: 85% is where the kubelet starts to delete images, so the rule reports the real limit of the node, and the prune lowers the usage.
- **Print the `kubectl exec` commands of a dry run for each gateway target.**: A dry run makes no request, so it cannot read the node of each pod, and the target of each deployment is in the repository files.
- **Put the README test at `tests/k8s/test_k8s_ollama_models.py`.**: The tests of the k8s documents and profiles live under `tests/k8s/`, and a test module flat under `tests/` is refused.
- **Read the two manifests through the defaults of `src/devops_cli/config/defaults.py`.**: The CLI already resolves the k8s profiles from the checkout that way, as `devops ai gateway render` does.
- **Make the planner pure: it takes the two manifest texts, the pod labels and the `ollama list` texts as arguments.**: The tests then assert the plan offline, with no client and no cluster.

## Rejected alternatives

- **Delete the files of the model directory from a pod.**: It leaves a manifest that names a missing blob, so the next load of that model fails.
- **Lower `LocalPathNodeDiskHigh` to 75%.**: The rule would fire where the kubelet does nothing, and `k8s/README.md:376:At 85% the kubelet starts to delete unused images.` names 85% as the limit.
- **Run the prune from a nightly CronJob.**: It removes a model that a person pulled on purpose within one day, and it needs a token and RBAC in namespace `llm`.
- **Move the model store of the node to another disk.**: It is a host change that no command of this repository makes, and the issue hands it to a person.
- **Read the gateway config from ConfigMap `llm-gateway-config-<hash>` at run time.**: The hash changes with the config, and a dry run makes no request; the file in the checkout holds the same routes.
- **Extract the `api_base` parse of `src/devops_cli/k8s/gpu_thresholds.py:def _refuse_chat_routes` into a shared helper.**: That function answers whether a tier serves a generation model and raises a refusal; the plan needs the models of every target, so it reads the same file with the same host rule in its own module.
- **Add the keep set to a new file under `llm/profiles/`.**: It is a second source of truth for what the gateway config already states.
