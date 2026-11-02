# Tasks

## 1. Write the k3s upgrade plan into k8s/README.md

Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [ ] 1.1 Add a section `## Homelab k3s upgrade` to `k8s/README.md`. State the target: k3s 1.37.x, chosen by the owner from the k3s release page at execution time, because kubectl 1.37.1 is pinned and Kubernetes supports a server one minor version from its client. List the steps v1.31 to v1.32, v1.32 to v1.33, v1.33 to v1.34, v1.34 to v1.35, v1.35 to v1.36 and v1.36 to v1.37, because k3s supports only single-minor upgrades. For each step, name the checks that gate it: `kubectl version -o json` for the server and the client, `kubectl get nodes -o wide`, `helm list -A`, and for each chart the `helm template` of its values against the target, plus `kubectl get crd -o name` and `kubectl apply --dry-run=server` of the CRDs the cluster runs. Name the charts to check: Argo CD, k8s-monitoring, Loki, Traefik, NVIDIA DCGM exporter, Argo Workflows, Gitea, Qdrant, Open WebUI, Pyroscope, Tempo, OpenTelemetry collector, prometheus-operator-crds, Prometheus and Grafana. State the node order: drain the node, run the k3s install script with the target release, then uncordon. State the check after the last step: `devops k8s deploy-stack --stack devops` prints no skew warning. Replace the prerequisites paragraph that says the cluster stays outside the supported skew with a statement of the target and a link to the new section
  - Verification: `uv run devops ci docs` passes
- [ ] 1.2 k8s/README.md, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## 2. Hold the upgrade plan to its steps with a test

Reads: `k8s/README.md`. Changes: `tests/invariants/test_k8s_readme_upgrade_plan.py` (new).

- [ ] 2.1 Add `tests/invariants/test_k8s_readme_upgrade_plan.py`. It reads `k8s/README.md` and asserts the upgrade section names each step from v1.31 to v1.37 in order, names a check for each step, names the target 1.37.x and the pinned kubectl 1.37.1, and names `devops k8s deploy-stack --stack devops` as the check after the last step. Each assertion names the line that it needs, so a failure says what the document lost
  - Verification: `uv run devops ci test tests/invariants/test_k8s_readme_upgrade_plan.py` passes

## Criteria

- `k8s/README.md` holds the upgrade plan, with the check for each step.: group 1
- After the owner runs it, `devops k8s deploy-stack` prints no skew warning.: pending-person, The upgrade is a host change of the homelab owner: it runs the k3s install script on each node and no job of this repository reaches that host.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
