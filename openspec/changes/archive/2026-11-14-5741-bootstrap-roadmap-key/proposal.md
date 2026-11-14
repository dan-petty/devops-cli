# Proposal: #5741

## Why

The roadmap Service Deployment (`devops/roadmap-service`) reads `DEVOPS_CLI_AI_API_KEY` from key `api-key` of Secret `roadmap-service-llm-key` (#3685, #5703). Because Secret row `devops/roadmap-service-llm-key` has `required: false` in `CLUSTER_SECRETS`, `devops k8s push-secrets` skips it when no key is stored in the OS keyring. When the pod starts without the Secret, kubelet fails with `Error: secret "roadmap-service-llm-key" not found`. Setting up the virtual key manually requires four distinct low-level commands across kubectl, curl and devops-cli. A single CLI command `devops k8s bootstrap-roadmap-key` automates key minting, keyring persistence and Secret deployment. Closes #5741.

## What Changes

- Add command `devops k8s bootstrap-roadmap-key` under `src/devops_cli/commands/k8s/roadmap_key_bootstrap.py`.
- The command retrieves the LiteLLM master key from `Secret/llm/llm-gateway-secrets`, calls `POST /key/generate` on the gateway, stores the virtual key in the OS keyring under `roadmap_service.llm_key`, and pushes Secret `roadmap-service-llm-key` in namespace `devops`.
- Supports `--context`, `--models`, `--budget`, `--rpm`, `--alias`, `--force`, and `--dry-run`.
- Add test coverage in `tests/commands/k8s/test_bootstrap_roadmap_key.py`.
- Update `k8s/README.md` and CLI documentation to document the new command.
- The change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-service-deployment`: Add requirement for `devops k8s bootstrap-roadmap-key` automating virtual key minting and Secret provisioning.

## Impact

- CLI: New subcommand `devops k8s bootstrap-roadmap-key`.
- Keyring: Writes `roadmap_service.llm_key`.
- Cluster: Writes `Secret/devops/roadmap-service-llm-key`.
- Docs: Updates `k8s/README.md` and CLI documentation.

## Feasibility

Confirmed against the live cluster on 2026-11-14:
- Secret `llm-gateway-secrets` holds `master-key` in namespace `llm`.
- The LiteLLM gateway service answers at `llm-gateway.llm.svc.cluster.local:4000` / `https://ai.example.com` and supports `POST /key/generate`.
- `devops k8s push-secrets --only devops/roadmap-service-llm-key` successfully manages Secret `roadmap-service-llm-key` once `roadmap_service.llm_key` exists in keyring.

## Existing Tool Considered

LiteLLM provides `/key/generate` and `kubectl` manages secrets, but no existing command coordinates extracting the cluster admin key, calling the gateway API, updating the OS keyring, and pushing the Secret. Building this command reuses existing internal k8s and HTTP clients.
Cost: 100,000 agent tokens and 0.25 day.
