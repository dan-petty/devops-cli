# Proposal: #6066

## Why
Two workloads that serve traffic stop their route during a rollout or a node drain. `devops/mcp-server` uses `strategy: Recreate`, so each release stops the MCP calls of the running jobs until the new pod is ready, and its TCP readiness probe sends traffic to a pod that accepts a connection but cannot serve a tool. `llm/llm-gateway` runs one replica with no PodDisruptionBudget, and no document gives the reason. Closes #6066.

## What Changes
- The MCP server rolls with `RollingUpdate`, `maxSurge: 1` and `maxUnavailable: 0`.
- The HTTP app of the MCP server serves `GET /healthz` with no token, and the readiness probe calls it.
- `k8s/README.md` gives the reason for one gateway replica: each LiteLLM process keeps its own cooldowns (#5990). A test fails when the replica count, a shared cooldown store and a PodDisruptionBudget disagree.
- `docs/CLUSTER.md` and `SECURITY.md` describe the rollout and the health route.

## Capabilities
- `workload-rollout` (new): the rollout of the MCP server, its health route, and the replica rule of the gateway.

## Impact
A release of the MCP server no longer stops the MCP calls of a running job. The gateway does not change. A node drain still stops the gateway until its pod runs on another node, as the README states.

## Feasibility
`k8s/devops/mcp-server/deployment.yaml` holds `strategy: Recreate`, no volume claim, and TCP probes. `src/devops_cli/ai/mcp/remote.py` builds stateless endpoints (`stateless_http=True`), so two pods can serve at the same time. `k8s/llm/gateway/config.yaml` sets no `redis_host` in `router_settings`, so the cooldowns of the router stay in the process.

## Existing Tool Considered
Kubernetes `RollingUpdate` and an `httpGet` readiness probe cover the MCP server. The LiteLLM router can share cooldowns through Redis or Valkey (`router_settings.redis_host`); that change, with a second replica and a PodDisruptionBudget, waits for #5990 and is out of this change. The change builds one route of four lines.
