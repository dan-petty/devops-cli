# Proposal

## Why

The root disk of the control-plane node is about 86% used, and the Ollama model store holds 128 GiB of it. The kubelet deletes unused images at 85% used and evicts pods under DiskPressure, so the node must remove the models that no tier of the node serves, and must write down the models that each node keeps. #3654

## What Changes

- Add the capability `ollama-model-prune` with the keep rule, the per-node plan, the dry run, the written keep set and the stop on an unreadable model list.
- Add the planner `src/devops_cli/k8s/ollama_prune.py`: it builds the keep set of each node from the gateway routes and the tier Services of the llm stack, and from the tier pod of each node.
- Add `devops k8s ollama prune` with `--plan`, `--dry-run` and `--context` in `src/devops_cli/commands/k8s/ollama.py`, registered beside the volume group at `src/devops_cli/commands/k8s/__init__.py:140:app.add_typer(volume_app, name="volume", help=HELP.k8s.volume_app)`.
- Add the keep-set table to the GPU Placement section of `k8s/README.md`, and `tests/k8s/test_k8s_ollama_models.py`, which fails when the table and the gateway config differ.
- Add the heading constant, the help and the messages of the command to `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py` and `src/devops_cli/lang/en/messages.py`.
- Keep `LocalPathNodeDiskHigh` at 85%: `k8s/README.md:376:At 85% the kubelet starts to delete unused images.` states the limit of the node, and the prune lowers the usage of the disk instead of the rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ollama-model-prune`: The prune keeps the models that the tiers of a node serve, The plan names each node and each model once, A dry run of the prune makes no request, The written keep set matches the gateway config, An unreadable model list stops the node

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/k8s/ollama_prune.py`, `src/devops_cli/commands/k8s/ollama.py`, `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `k8s/README.md`
- Tests: `tests/k8s/test_k8s_ollama_models.py`, `tests/k8s/test_k8s_ollama_prune.py`, `tests/commands/k8s/test_k8s_ollama_prune.py`

## Feasibility

- The premise holds. Probe, quoted: The path `k8s/README.md` is a file of the staging commit. The README and the alert rule state one limit of the node: `k8s/README.md:376:At 85% the kubelet starts to delete unused images.` and `k8s/monitoring/prometheus-values.yaml:293:# At 85% used the kubelet starts to delete unused images (imageGCHighThresholdPercent), and`.
- Probe, quoted: The path `llm/gateway/config.yaml` is no file at the root of the staging commit. These files of the commit are candidates: `k8s/llm/gateway/config.yaml`, `openspec/config.yaml`. No commit in the history deleted or renamed it. The CLI already resolves that path at `src/devops_cli/config/defaults.py:1001:DEFAULT_LLM_GATEWAY_CONFIG_PATH: Final[Path] = Path("k8s/llm/gateway/config.yaml")`, so the plan reads the gateway config there and the issue can be built as written.
- Probe, quoted: The path `tests/test_k8s_ollama_models.py` is no file of the staging commit. No commit in the history deleted or renamed it. The plan creates that test at `tests/k8s/test_k8s_ollama_models.py`, the folder that mirrors the k8s code.
- Probe, quoted: `LocalPathNodeDiskHigh` has no definition at the staging commit. The rule is YAML in `k8s/monitoring/prometheus-values.yaml`, so the plan keeps it at 85% and lowers the usage of the disk instead.
- The routing is in the file: `k8s/llm/gateway/config.yaml:16:api_base: http://ollama-48gib-fast.llm.svc.cluster.local:11434` sends `qwen3.8:27b` to the fast tier, and `k8s/llm/profiles/services.yaml:262:llm.devops.io/speed-tier: fast` is a selector that the tier pod carries.
- `search_code` for `llm.devops.io/provider` shows the label at `k8s/llm/profiles/services.yaml:12:llm.devops.io/provider: ollama`, and `src/devops_cli/config/constants.py:1082:CONST_K8S_OLLAMA_PROVIDER_LABEL: Final[tuple[str, str]] = ("llm.devops.io/provider", "ollama")` already names the pair.
- `search_code` for `ollama prune` returned no match, so the command and its module are new; the command group registers a sub-app at `src/devops_cli/commands/k8s/__init__.py:140:app.add_typer(volume_app, name="volume", help=HELP.k8s.volume_app)` and the prune joins it the same way.
- The dry-run class has a model at `src/devops_cli/commands/k8s/volume.py:59:@dry_run_class("request-plan")`, which the prune command copies.
- The first checks against the real system: `kubectl -n llm get pods -l llm.devops.io/provider=ollama -o wide` names the node of each tier pod, and `kubectl -n llm exec -i <tier-pod> -- ollama list` lists the models of the store of that node.
- The first checks of the change: `uv run devops k8s ollama prune --plan` prints each node and the models it would remove, and `uv run devops ci test tests/k8s/test_k8s_ollama_prune.py` runs offline.
- `gateway_targets` needs a checkout of the repository: it reads the gateway config of the llm stack.
- `service_selectors` needs a checkout of the repository: it reads the tier Services of the llm stack.
- `read_ollama_pods` needs a client of the cluster: it lists the pods labelled `llm.devops.io/provider=ollama` in namespace `llm`.
- `run_ollama_prune` needs a client of the cluster: it runs `kubectl exec` and `ollama rm` in one pod of each node.
- `render_prune_requests` needs a checkout of the repository for the two manifests and no client, because a dry run makes no request.
- The earlier reply named two files that no group changes in `what_changes`; this reply names there only the paths that a group changes or creates, and reads those two files instead.

## Existing Tool Considered

Ollama is the open, maintained tool: `ollama list` and `ollama rm` (`DELETE /api/delete`) list and remove a model, and its FAQ names the model store. It holds no keep set and has no plan mode, so the change builds about 250 lines of Python around it: 25k tokens to build, 5k tokens a year to keep and repair, and 4 hours of elapsed time. The change deletes no internal code.

## Dependencies

- #3937 also changes `k8s/README.md`, where it adds the Crawl4AI token to the cluster secrets.
- #3946 also changes `k8s/README.md`, where it states the request budget of the Service.
- #3948 also changes `k8s/README.md`, where it describes the web search chain.
- #3660 waits on this change: it confirms on the live node that the root disk stays under 75% for 7 days after the prune.
