# Proposal

## Why

Issue #1971: the tune paragraph of `k8s/README.md` tells the reader to copy recommended weights into `litellm_params.weight`. The gateway has no weights. A reader who follows the paragraph looks for a setting that the gateway does not read.

## What Changes

- The tune paragraph of `k8s/README.md` says what `devops ai gateway tune` reports for each deployment: the engine, the GPUs, the capacity and the cost. It says that the `least-busy` router reads none of these numbers, and that the gateway uses neither the weight nor the concurrency that the command also prints.
- Three more texts that describe gateway weights are corrected:
  - the `qwen3-coder:30b` and `gpt-oss:20b` item in `k8s/README.md`;
  - two comments in `k8s/llm/gateway/config.yaml`;
  - the model comparison paragraph of `docs/SELF_IMPROVEMENT.md`.
- No code changes. The change only corrects documents and comments, so it sets `skip_specs: true`.
- The comment change in `config.yaml` changes the hash of the generated ConfigMap `llm-gateway-config`, so Kubernetes rolls the gateway once when Argo CD syncs the merge (`k8s/llm/gateway/kustomization.yaml`). The Deployment has one replica and the default rolling update, so the new pod starts before the old one stops.
- This change fits one pull request.

## Impact

- `k8s/README.md`, `k8s/llm/gateway/config.yaml`, `docs/SELF_IMPROVEMENT.md`.

## Feasibility

On origin/main `c96dbfe3` (2026-10-29):

- `k8s/llm/gateway/config.yaml` sets `router_settings.routing_strategy: least-busy`. Its `embedding` routing group uses `simple-shuffle`. No deployment sets `weight` or `max_parallel_requests`; `weight` occurs only in two comments.
- `_print_tune_report` in `src/devops_cli/commands/ai_gateway.py` prints, for each deployment, the engine, the GPUs, the capacity at the best concurrency and the cost, and also a current weight, a recommended weight and a recommended concurrency. Its footer tells the user to set `litellm_params.weight`. #2592 corrects the command; this change corrects only the documents.

## Existing Tool Considered

None is needed: the change corrects text. It deletes the instruction to copy weights into `litellm_params.weight`.
