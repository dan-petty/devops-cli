# Proposal: #4496

## Why
The order rule for `ai.decision_model` checks only the Service image. Three workloads load the ConfigMap `devops-cli-config`, each with its own image: Deployment `roadmap-service`, CronJob `devops-cli-runner` and its Jobs, and Deployment `mcp-server`. `AIConfig` refuses a key that it does not know, so a runner image or an MCP server image that is older than the key stops at the load of the settings. The texts in `docs/roadmap/stage.md` and `k8s/devops/configmap.example.yaml` let a person add the key while one of these images is older. Closes #4496.

## What Changes
- The last paragraph of "The verify screen" in `docs/roadmap/stage.md` names the three images and gives two checks before a person adds `ai.decision_model`: the `Live since` comment of the release on #4397 (Service and runner digests), and `kubectl -n devops exec deploy/mcp-server -- devops config get ai.decision_model` with an empty value and no error.
- The comment of `ai` in `k8s/devops/configmap.example.yaml` says the same and points to `docs/roadmap/stage.md`.
- The change alters only documents and a YAML comment, which no consumer observes, so it has no spec delta (`skip_specs: true`).

## Capabilities
- None.

## Impact
- `docs/roadmap/stage.md`, `k8s/devops/configmap.example.yaml`.
- The start condition in the body of #4446 has the same gap. A pull request cannot change an issue body, so #4507 holds that change.
- The change fits one pull request.

## Feasibility
- Source on `main` at 5f75d256: `k8s/devops/roadmap-service/deployment.yaml`, `k8s/devops/cronjob-runner.yaml` and `k8s/devops/mcp-server/deployment.yaml` each mount ConfigMap `devops-cli-config` and set `DEVOPS_CLI_CONFIG`. Their images are `service`, `runner` and `mcp-server`.
- `src/devops_cli/roadmap/release_comments.py` posts `Live since` when the Service and runner image digests of a release run in the cluster. It does not read the MCP server digest.
- `Dockerfile` builds `mcp-server` `FROM runner`, and the runner stage has `ENTRYPOINT ["devops"]`, so `devops config get` runs in the MCP server pod.
- `ai.decision_model` came with #4397 in v0.111.0 (`git tag --contains b73e97ab`).

## Existing Tool Considered
- The `Live since` comment of `release_comments.py` and `devops config get` already exist and cover the checks. The change builds no code and deletes none.
