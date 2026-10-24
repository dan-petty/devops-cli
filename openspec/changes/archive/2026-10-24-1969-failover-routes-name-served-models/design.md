# Design

## Context

`DEFAULT_GATEWAY_ROUTES` in `src/devops_cli/ai/gateway.py` is the route table that the `devops ai gateway` commands start from. The gateway config, `k8s/llm/gateway/config.yaml`, names the model that each deployment sends to each Ollama Service. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- Each default route and each failover route names a model that its tier serves, and a test keeps it so.

**Non-Goals:**

- A route table that `devops ai gateway` saved before this change keeps its old routes (#2045).

## Decisions

- **The routes stay in the CLI, and a test binds them to the gateway config.** Rejected: read the routes from the gateway config at run time. The wheel and the service image hold only `src/devops_cli` (`[tool.hatch.build.targets.wheel]`, `COPY src/` in the `Dockerfile`), so the CLI cannot read `k8s/llm/gateway/config.yaml`. Rejected: move the config into `src/devops_cli`. The `configMapGenerator` of `k8s/llm/gateway/kustomization.yaml` reads `config.yaml` from its own directory.
- **A failover to `direct-ollama` keeps the model of the default route.** The route calls the default Ollama tier without the gateway, so the model of the default route is the one model that the tier is known to hold. Rejected: one fixed fallback model. `qwen2.5-coder:7b` was such a model, and it sent an embedding failover to a chat model.
- **The capability gate tests make their own small route.** No default route is now below the 30B floor of a virtual model that fails over to it, so the tests write a route table whose `devops-coder` route is `gpt-oss:20b`.

## Risks / Trade-offs

- [A model leaves a tier] → The route check fails on the next pull request that changes the config or the routes, and the author moves the route.
- [A saved route table keeps the old routes] → #2045 makes the saved table keep only failover state.
