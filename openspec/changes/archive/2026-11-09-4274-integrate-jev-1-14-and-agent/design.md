# Design

## Decisions

- **Use `SystemOneModel` and `DecisionModel` from `pydantic_ai`.** `resolve_pydantic_ai_model` resolves `typesafe/jev-1.14` (and `system-one:` / `typesafe:` prefixes) to `SystemOneModel` with `typesafe_model_profile`, and resolves `"auto"` or `"auto:<model>"` to a `DecisionModel` backed by a `FallbackModel`. This reuses `pydantic_ai`'s native hand-off when a run requires free-form text generation after tool selection.
- **Keep all three skill roots identical.** `tests/invariants/test_skills.py` checks `.agents/skills/`, `.claude/skills/`, and `.kilocode/skills/` so Antigravity, Claude Code, and Kilo Code load the same five project skills.
- **Run `mcp-server` under `devops-default-perimeter` with dedicated ingress and client egress policies.** `k8s/devops/mcp-server/networkpolicy.yaml` admits TCP 8001 from `roadmap-service` and `devops-cli-runner`, and `networkpolicy-client.yaml` grants those two workloads egress to `mcp-server` on TCP 8001.

## Rejected alternatives

- **Custom `/v1/systemone` HTTP client.** Rejected because `pydantic_ai.models.system_one.SystemOneModel` and `DecisionModel` already implement batching, probability normalization, choice chunking (255 options), and 10-level scoring.
- **Exposing `mcp-server` outside namespace `devops`.** Rejected because cluster jobs and the roadmap Service run in namespace `devops`, and keeping the service ClusterIP-only with pod-selector NetworkPolicies preserves the zero-trust perimeter.
