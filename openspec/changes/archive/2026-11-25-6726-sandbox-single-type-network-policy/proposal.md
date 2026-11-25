# Proposal: #6726

## Why

`SandboxNetworkConfig.to_k8s_network_policy` (`src/devops_cli/sandbox/models.py:460-493`) generates one Kubernetes `NetworkPolicy` with `policyTypes: ["Ingress", "Egress"]`. On kube-router, a dual-type `NetworkPolicy` can let egress rules bypass ingress restrictions between selected pods (#6708), and runtime-generated sandbox policies must follow the single-type policy rule. Closes #6726.

## What Changes

- Change `SandboxNetworkConfig.to_k8s_network_policy` in `src/devops_cli/sandbox/models.py` to return a tuple of two single-type `NetworkPolicy` dicts: an `Ingress` policy first (`-ingress` suffix) and an `Egress` policy second (`-egress` suffix), each keeping the `podSelector` and its own direction rules (`ingress` or `egress` only), trimming long base names to stay within `CONST_MAX_K8S_RESOURCE_NAME_LENGTH` (253 chars) as valid DNS subdomains.
- Update `network_policy` in `src/devops_cli/commands/sandbox.py` to dump the two policies as multi-document YAML (`yaml.safe_dump_all`).
- Update `tests/sandbox/test_sandbox_network_config.py`, `tests/sandbox/test_sandbox_policy_properties.py`, and `tests/commands/test_sandbox_network_policy.py` for the two-policy tuple and multi-document YAML, and add single-type pair, isolated deny-all, rule-preservation, and distinct DNS subdomain name tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sandbox-egress`: Render one Ingress-only policy and one Egress-only policy for every sandbox network mode with distinct valid DNS subdomain names and preserved directional rules.

## Impact

- Code: `src/devops_cli/sandbox/models.py`, `src/devops_cli/commands/sandbox.py`.
- Tests: `tests/sandbox/test_sandbox_network_config.py`, `tests/sandbox/test_sandbox_policy_properties.py`, `tests/commands/test_sandbox_network_policy.py`.
- Specs: `openspec/specs/sandbox-egress/spec.md` via OpenSpec archive.

## Feasibility

- Inspected `src/devops_cli/sandbox/models.py:480-493`: `SandboxNetworkConfig.to_k8s_network_policy` returns one dict with `"policyTypes": ["Ingress", "Egress"]`. Note the issue mentions `SandboxNetworkPolicy`, which is named `SandboxNetworkConfig` in code.
- Inspected `src/devops_cli/commands/sandbox.py:1115-1119`: `network_policy` is the sole production caller and writes `yaml.dump(policy_dict, sort_keys=False)`.
- Inspected `tests/gate/k8s_checks/network_policies.py:243-252`: `dual_type_problems` already defines the `<name>-ingress` and `<name>-egress` convention.
- First check against the real system: `uv run devops ci test tests/sandbox/test_sandbox_network_config.py tests/commands/test_sandbox_network_policy.py` fails on the base once the single-type tests are added.

## Existing Tool Considered

The alternatives check of 2026-11-22 in #6726 returned `none` and named no external tool; no policy engine emits split `Ingress`/`Egress` pairs from `SandboxNetworkConfig`. Updating `SandboxNetworkConfig.to_k8s_network_policy`, `commands/sandbox.py`, and the three sandbox test files takes ~150 lines (~6,000 tokens and ~1-2 hours to build and keep).
