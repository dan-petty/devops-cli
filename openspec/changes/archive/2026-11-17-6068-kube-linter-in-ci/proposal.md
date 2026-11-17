# Proposal: #6068

## Why
No CI job runs kube-linter. The Security Scan step of `ci.yml` runs `devops scan report`, and the Static Analysis runner has no `kube-linter`, so the log says "Scanner 'kubelinter' was not run". On 2026-11-17 the owner deleted about 100 tests that checked security controls of the manifests (#6060, #6075): network perimeters, no ServiceAccount token, security contexts, pins and prune protection. Rule CT2 of `docs/SERVICE_PATTERNS.md` says that a schema or policy tool checks a manifest. Until a policy tool runs in CI, only `trivy config` and review check those controls. Closes #6068.

## What Changes
- `devops k8s lint` with no TARGET builds each path source of the Argo CD Applications of the environment tree, as Argo CD builds it, into one folder, and lints the folder in one kube-linter run with the `.kube-linter.yaml` of the repository. A finding, or a run that did not happen, exits 1. With a TARGET, the command lints that path as before.
- `.kube-linter.yaml` turns on the default checks of kube-linter, the checks that the service patterns name (`default-service-account`, `no-liveness-probe`, `no-readiness-probe`, `no-rolling-update-strategy`, `non-isolated-pod`), and a custom check `pvc-prune-protection`.
- A new row of `devops ci`, `kube-linter`, runs `devops k8s lint`. The Static Analysis job installs the pinned kube-linter of `tools.lock` and runs the row. The Security Scan step skips kube-linter, which reads only the root kustomization of a tree.
- Each finding on the manifests of 2026-11-17 is fixed or has the annotation `ignore-check.kube-linter.io/<check>` with its reason. Six Deployments and the GPU feature discovery DaemonSet set the rolling strategy that Kubernetes already gave them. Each exception names the issue that removes it, or #6068 when the object cannot meet the check.
- `devops k8s image-pins` builds a path source with the same function.
- The service patterns, the routine tasks and the knowledge base name the new row.

## Capabilities
- `k8s-lint`: a requirement for the lint of the environment tree is added.
- `ci-gate-rows`: a requirement for the `kube-linter` row is added.

## Impact
- Code: `src/devops_cli/commands/k8s/security_audit.py`, `src/devops_cli/k8s/app_render.py` (new), `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/security/kubelinter.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/roadmap/runner_tools.py`, the texts.
- CI: the Static Analysis job installs kube-linter. The row takes about 10 s.
- Manifests: annotations on 16 objects, a patch in `k8s/llm/profiles/kustomization.yaml` that annotates the 10 Ollama tiers, and an explicit rolling strategy on 7 workloads. No pod template changes, so no pod starts again.
- The Helm chart sources are not linted: #6106.

## Feasibility
- kube-linter 0.8.3 (the pin of `tools.lock` and `.devcontainer/Dockerfile`) run on the builds of the 15 path sources with this config gave 56 findings before the fixes and annotations, and 0 after.
- `kube-linter lint k8s` reads only the root kustomization of `k8s/`: 13 reports from 4 files of `cloudflared`, `cert-manager` and `cnpg-system`. So the tree must be built first.
- kube-linter has no exception for one object in its config (`checks.include` and `checks.exclude` only). Its exception for one object is the annotation `ignore-check.kube-linter.io/<check>`.
- The values of `argocd-image-updater`, `cloudnative-pg`, `dcgm-exporter`, `mattermost-operator` and `open-webui` have no key that annotates their workloads, so a chart finding there cannot get a narrow exception. The 19 chart sources give 113 findings. #6106 takes them.

## Existing Tool Considered
- kube-linter (stackrox/kube-linter, Apache-2.0) is the tool of the issue, and the repository already runs it through `src/devops_cli/security/kubelinter.py`. Kustomize, through `kubectl kustomize`, builds the sources, as the Argo CD gate and `devops k8s image-pins` do. The code is a small function that reuses the source trees of `devops_cli.k8s.app_sources`. Cost: about 3M agent tokens and 5 hours.
