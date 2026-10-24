# Proposal

## Why

Issue #990: `devops k8s bootstrap` help text states that the cluster configures Calico for network policy enforcement.
`_start_minikube` in `src/devops_cli/commands/k8s/cluster_runtime.py` starts Minikube without a `--cni` argument.
Minikube falls back to its default CNI plugin, which does not enforce `NetworkPolicy` resources.
Sandbox egress policies and namespace perimeters silently do not enforce network rules without Calico.

## What Changes

- Update `_start_minikube` in `src/devops_cli/commands/k8s/cluster_runtime.py` to include `--cni=calico` in both GPU and fallback Minikube start command invocations.
- Update `_start_minikube` status messages and dry-run messages to reflect `--cni=calico`.
- Wire `HELP.k8s.bootstrap` help string explicitly to the `bootstrap` command in `src/devops_cli/commands/k8s/__init__.py`.
- Update the `bootstrap` docstring in `src/devops_cli/commands/k8s/bootstrap.py` to match the Calico description in `HELP.k8s.bootstrap`.
- Update Minikube manual start hints in `src/devops_cli/lang/en/messages.py` to include `--cni=calico`.
- Add an offline test in `tests/test_k8s_bootstrap.py` that pins the Minikube argv to `--cni=calico` and asserts that help text matches.
- Update existing tests in `tests/test_k8s_bootstrap.py` and `tests/test_devcontainer.py` that assert `minikube start` invocations and messages.
- Regenerate documentation using `devops docs generate --sync-readme`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `k8s-bootstrap`: Minikube cluster startup with Calico CNI for network policy enforcement.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/k8s/cluster_runtime.py`: Starts Minikube with `--cni=calico`.
- `src/devops_cli/commands/k8s/__init__.py`: Connects `HELP.k8s.bootstrap` to the command definition.
- `src/devops_cli/commands/k8s/bootstrap.py`: Aligns command docstring with `HELP.k8s.bootstrap`.
- `src/devops_cli/lang/en/messages.py`: Aligns Minikube start guidance commands with `--cni=calico`.
- `tests/test_k8s_bootstrap.py`: Pins Minikube start argument list and verifies help text.
- `tests/test_devcontainer.py`: Updates Minikube start argument assertions.
- `docs/CLI_REFERENCE.md` and `README.md`: Synchronized documentation.

## Feasibility

- Minikube version `v1.35.*` supports `--cni=calico` natively as verified via `minikube start --help`.
- Upstream Minikube documentation confirms `--cni=calico` installs and configures the Calico CNI plugin.
- In-process unit tests in `tests/test_k8s_bootstrap.py` verify subprocess argument lists offline through process doubles.

## Existing Tool Considered

Minikube's built-in `--cni=calico` parameter satisfies the requirement directly without extra installation scripts or custom CNI manifests.
No additional third-party tool is necessary.
No internal code is deleted.
