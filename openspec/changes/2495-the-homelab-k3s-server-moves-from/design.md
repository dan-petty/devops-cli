# Design

## Decisions

- **Write the plan into the existing `k8s/README.md` rather than a new document.**: The issue names that file, and the prerequisites section there already holds the skew statement that the plan replaces.
- **Target k3s 1.37.x, chosen by the owner at execution time.**: kubectl 1.37.1 is the pinned client, and Kubernetes supports a server one minor version from it, so 1.36 to 1.38 is the range and 1.37.x is the nearest.
- **Step one minor version at a time: v1.31 to v1.32 through v1.36 to v1.37.**: k3s supports only single-minor upgrades.
- **Give each step the chart and CRD checks that gate it, with `helm template` and `kubectl apply --dry-run=server`.**: A chart or CRD that the newer API server rejects stops the step, and the check finds it before the node changes.
- **Add a test that reads `k8s/README.md` and asserts each step and its check.**: The document is the only deliverable, so a test keeps the plan complete when a later edit touches the file.
- **Leave the kubectl pin in `tools.lock` alone.**: `k8s/README.md` states that 1.31 and 1.32 are end of life and the devcontainer minikube runs a current release, so the client stays where it is and the server moves to it.

## Rejected alternatives

- **Install the system-upgrade-controller and plan a Plan custom resource.**: The issue's Existing Tool Considered names it, and the plan needs a CRD and a controller deployment that stays in the cluster after a one-time upgrade of one node set.
- **Jump from v1.31 straight to v1.37.**: The issue states that k3s supports only single-minor upgrades, so one jump leaves the datastore and the API server in an unsupported state.
- **Downgrade the devcontainer kubectl to 1.31 or 1.32.**: `k8s/README.md` states: "We do not pin `kubectl` to 1.31 or 1.32, because both versions are end of life and the devcontainer minikube runs a current release."
