# Tasks

## 1. Split SandboxNetworkConfig policies into single-type Ingress and Egress objects

Kind: behavior. Reads: `src/devops_cli/sandbox/models.py`, `src/devops_cli/commands/sandbox.py`, `tests/gate/k8s_checks/network_policies.py`. Changes: `src/devops_cli/sandbox/models.py`, `src/devops_cli/commands/sandbox.py`, `tests/sandbox/test_sandbox_network_config.py`, `tests/sandbox/test_sandbox_policy_properties.py`, `tests/commands/test_sandbox_network_policy.py`.

- [x] 1.1 Write failing tests in `tests/sandbox/test_sandbox_network_config.py`, `tests/sandbox/test_sandbox_policy_properties.py`, and `tests/commands/test_sandbox_network_policy.py` covering every `SandboxNetworkMode` single-type pair, preserved `podSelector` and directional rules, isolated deny-all empty lists, distinct valid DNS subdomain names including trimmed long names, and multi-document YAML output from `devops sandbox network-policy` and `sandbox_network_policy`.
  - Verification: `$ uv run devops ci test tests/sandbox/test_sandbox_network_config.py tests/sandbox/test_sandbox_policy_properties.py tests/commands/test_sandbox_network_policy.py` fails on base
- [x] 1.2 Update `SandboxNetworkConfig.to_k8s_network_policy` in `src/devops_cli/sandbox/models.py` to return `(ingress_policy, egress_policy)` with single-type `policyTypes` and trimmed DNS subdomain names (`-ingress` / `-egress`), and update `network_policy` in `src/devops_cli/commands/sandbox.py` to write `yaml.safe_dump_all(policies, sort_keys=False)`.
  - Verification: `$ uv run devops ci test tests/sandbox/test_sandbox_network_config.py tests/sandbox/test_sandbox_policy_properties.py tests/commands/test_sandbox_network_policy.py` passes
