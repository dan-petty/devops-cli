# Design

## Decisions

- **Return `(ingress_policy, egress_policy)` from `SandboxNetworkConfig.to_k8s_network_policy`**: Keep one method and change its return type to `tuple[dict[str, Any], dict[str, Any]]` (Ingress-only first, Egress-only second), matching `src/devops_cli/sandbox/models.py:460` callers (`commands/sandbox.py:1115`). Use a shared `_policy` helper so both dicts stay uniform with no duplicated boilerplate.
- **Name the two resources `<name>-network-policy-ingress` and `<name>-network-policy-egress`**: Append `-ingress` and `-egress` to `f"{name}-network-policy"`; if the combined length exceeds `CONST_MAX_K8S_RESOURCE_NAME_LENGTH` (253), trim the base prefix and strip trailing `.` and `-` before appending the suffix so every generated name satisfies `CONST_K8S_SUBDOMAIN_RE`.
- **Emit multi-document YAML in `devops sandbox network-policy`**: Use `yaml.safe_dump_all(policies, sort_keys=False)` in `src/devops_cli/commands/sandbox.py:1118` so both policies stream cleanly to `kubectl apply -f -` and parse via `yaml.safe_load_all`.

## Rejected alternatives

- **Add a plural method while keeping `to_k8s_network_policy` singular**: Rejected, because leaving a dual-type generator method invites callers to emit unsafe policies.
- **Hash long sandbox names when truncating**: Rejected, because deterministic prefix trimming keeps readable Kubernetes resource names while staying within `CONST_MAX_K8S_RESOURCE_NAME_LENGTH` (253 chars).
