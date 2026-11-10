# Proposal

## Why

Issue #4354: Deployment `mcp-server` in namespace `devops` crash-loops. The server fails closed (SECURITY.md, "MCP Server on the Network") and refuses to start without `mcp.token`. No part of the repository makes that token: the secret table has no row for it, Secret `devops/devops-cli` has no key for it, and the Deployment has no reference to it. The clients have the same gap. The stage job reads `mcp.stage_token` and the implement job reads `mcp.implement_token`, and no row writes either.

## What Changes

- Add Secret `devops/mcp-server` to the secret table. Its key `DEVOPS_CLI_MCP_TOKEN` reads the keyring entry of `mcp.token`, is generated with `token_urlsafe(32)` when missing, and restarts `deployment/mcp-server`. This is the pattern of `devops/crawl4ai`.
- Add the keys `DEVOPS_CLI_MCP_STAGE_TOKEN` and `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN` to Secret `devops/devops-cli`. Both are optional, read the same keyring entry, and adopt from `devops/mcp-server`. The server accepts one token, so the three values are equal.
- Set the variable `DEVOPS_CLI_MCP_TOKEN` in Deployment `mcp-server` with a `secretKeyRef`.
- Set `roadmap.mcp.url` in `k8s/devops/configmap.example.yaml`. The switches `roadmap.stage.mcp` and `roadmap.implement.mcp` stay off.
- Add a test that fails when a `secretKeyRef` of a manifest names a key that its row of the table lacks.
- Update `k8s/README.md`, `SECURITY.md` and the description of `mcp.token`, and regenerate `docs/ENV_VARS.md`. SECURITY.md named the LiteLLM gateway as the one caller. The callers are the roadmap Service and the runner Jobs.
- The change carries a spec delta: the secret table, a manifest and a service setting are observable.

## Capabilities

### New Capabilities

- `mcp-server-token`: how the token of the MCP server reaches the cluster.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/config/env.py`.
- `k8s/devops/mcp-server/deployment.yaml`, `k8s/devops/configmap.example.yaml`.
- `k8s/README.md`, `SECURITY.md`, `docs/ENV_VARS.md`.
- A person runs `devops k8s push-secrets` after the merge. No agent writes a Secret.

## Feasibility

Read on 2026-11-10.

- The pod log of the Deployment holds one line: "Refusing to start the streamable-http transport: no bearer token is set." `src/devops_cli/ai/mcp/remote.py` raises it from `check_token` when `get_mcp_token` returns nothing. The credential `mcp.token` reads the variable `DEVOPS_CLI_MCP_TOKEN`, and the token needs at least 32 characters.
- The key names of Secret `devops/devops-cli` hold no MCP key (checked by key name only, no value was read).
- `src/devops_cli/roadmap/mcp.py` sends `get_mcp_stage_token()` to `/planning/mcp` and `get_mcp_implement_token()` to `/implementation/mcp`. The variables are `DEVOPS_CLI_MCP_STAGE_TOKEN` and `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN`. The runner CronJob and the Service load Secret `devops-cli` with `envFrom`, so a key of that Secret is a variable of the pod.
- `BearerTokenVerifier` compares one digest, so the server cannot accept a separate token for each role.
- The container command (`mcp serve --transport streamable-http --host 0.0.0.0 --port 8001 --allow-remote`) matches the image entrypoint `devops`, the container port and both probes (TCP 8001).

## Existing Tool Considered

The secret table and `devops k8s push-secrets` are the tool, and `devops/crawl4ai` is the pattern. The change builds no new mechanism: it adds rows and one `secretKeyRef`, and one invariant test over the manifests.
