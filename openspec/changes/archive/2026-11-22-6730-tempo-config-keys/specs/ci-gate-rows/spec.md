## ADDED Requirements

### Requirement: The charts row renders the chart sources, and the k8s row stays local
The table of `devops ci` SHALL hold a row `charts` that runs the `main` of `tests/gate/charts.py`. The row SHALL render the chart source of an Argo CD Application with `helm template` once, and every check of the row SHALL read that one render. A check that starts `helm` or a container engine, or that needs the network, SHALL be in the `charts` row and not in the `k8s` row, so that the `k8s` row needs only `kubectl` and the files of the checkout.

#### Scenario: Two checks read one chart render
- **WHEN** the two Tempo checks of the `charts` row ask for the render of `k8s/argocd/apps/tempo.yaml`
- **THEN** `helm template` runs once for that Application

#### Scenario: The k8s row starts no helm and no docker
- **WHEN** I run `uv run devops ci --check --only k8s` with a `helm` and a `docker` first on PATH that exit 1
- **THEN** The row passes
