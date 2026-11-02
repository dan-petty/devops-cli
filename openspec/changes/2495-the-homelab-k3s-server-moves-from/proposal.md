# Proposal

## Why

The homelab cluster runs k3s v1.31.4 and the devcontainer pins kubectl 1.37.1, so each `devops k8s` command runs outside the skew that Kubernetes supports and the cluster misses the security fixes of newer minor versions (#2495). The plan of the upgrade, with the check before each step, exists nowhere in the repository.

## What Changes

- `k8s/README.md` gains a section that holds the k3s upgrade plan: each single-minor step from v1.31 to v1.37 and the check to run before it.
- `k8s/README.md` names the target release range (1.37.x, within one minor version of kubectl 1.37.1) and the chart and CRD checks that gate each step.
- The prerequisites paragraph that says the homelab stays outside the supported skew states the target and points to the plan.
- A test reads `k8s/README.md` and fails when a step or its check is missing, so the plan cannot rot silently.
- The change carries a spec delta because `k8s/README.md` is a document outside `docs/`, and the plan it holds is what a reader observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `homelab-k3s-upgrade-plan`: The upgrade plan names each step and its check, The plan names the target and the skew it closes

### Modified Capabilities

None.

## Impact

- Documents: `k8s/README.md`
- Tests: `tests/invariants/test_k8s_readme_upgrade_plan.py`

## Feasibility

- `search_code` with `skew` returned the warning text in `src/devops_cli/commands/k8s/` and the paragraph in `k8s/README.md`: "Kubernetes supports `kubectl` within one minor version of the API server. The `tools.lock` file tracks a current `kubectl` release. The homelab cluster runs Kubernetes 1.31 (`v1.31.4+k3s1`), which stays outside the supported skew range until dan-petty/homelab#3 lands." The premise of the issue is that line.
- `read_file` of `k8s/README.md` showed the file at the staging commit with its `## Prerequisites` section, so the plan goes in an existing document and `probes` confirms the path is a file of the commit.
- `search_code` with `k8s/README.md` showed the tests that read it, so the new plan can be asserted offline by a test in the same shape.
- The first checks against the real system, each run by the owner on the homelab host before a step: `kubectl version -o json` on the server and the client, `kubectl get nodes -o wide`, `helm list -A` and `kubectl get crd -o name`. After the last step: `devops k8s deploy-stack --stack devops --dry-run` must print no skew warning.
- The upgrade itself is a host change of the owner, so the repository delivers the plan only; nothing here can run it.

## Existing Tool Considered

The k3s install script that Rancher documents at `https://docs.k3s.io` upgrades one node to a named k3s release and covers this single-cluster upgrade. Rancher's system-upgrade-controller also covers it, but adds a CRD and a controller deployment that a one-time upgrade of one cluster does not need. Nothing is built: the deliverable is the plan document.
