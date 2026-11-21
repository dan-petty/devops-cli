## ADDED Requirements

### Requirement: deploy-stack applies the builds of the path sources of the Applications of each stack
`devops k8s deploy-stack` SHALL build each path source of each Argo CD Application that `APPLICATIONS_BY_STACK` names for a selected stack, with Kustomize. A source of the `origin` of the checkout of the tree SHALL read the checkout, and a source of another repository SHALL be fetched at its `targetRevision` before the deploy touches the cluster. The deploy SHALL apply each build that holds an object with `kubectl apply -f -` before the charts.

#### Scenario: The build of a path source with a component is applied before the charts
- **WHEN** the tree `<tmp>/env` holds the Application `logging` with the path source `env/logging`, whose kustomization takes the local component `env/components/perimeter`, `kubectl kustomize` of `<tmp>/env/logging` gives two NetworkPolicies, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --no-push-secrets` runs on a cluster without Argo CD
- **THEN** the deploy starts `kubectl apply -f -` with the build as input before the `helm upgrade` of release `loki`

### Requirement: teardown-stack deletes the builds of the path sources
`devops k8s teardown-stack` SHALL build the same path sources as `deploy-stack`, and SHALL delete each build that holds an object with `kubectl delete -f - --ignore-not-found`, in the reverse order of the deploy, before the manifest paths and the Helm uninstalls.

#### Scenario: The teardown deletes the build before the chart
- **WHEN** the tree `<tmp>/env` holds the Application `logging` of the scenario above, and `devops k8s teardown-stack --stack logging --k8s-dir <tmp>/env` runs on a cluster without Argo CD
- **THEN** the teardown starts `kubectl delete -f - --ignore-not-found` with the build as input before the `helm uninstall` of release `loki`

### Requirement: deploy-stack stops on an Application that the tree does not hold
When the tree holds no Application of a name that `APPLICATIONS_BY_STACK` gives for a selected stack, `devops k8s deploy-stack` and `devops k8s teardown-stack` SHALL exit 1 and name the Application before they touch the cluster.

#### Scenario: A tree with no Application of the table
- **WHEN** the tree `<tmp>/env` holds the Application `loki` and no Application `logging`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** the command exits 1 and names the Application `logging`

### Requirement: The deploy-stack dry run lists the objects of each build
The dry run of `devops k8s deploy-stack` SHALL build each path source of the checkout as a local read. It SHALL list in `details.path_sources`, for each build in the order of the deploy, the Application, the `path` of the source, and the `kind`, `namespace` and `name` of each object of the build. The dry run of `devops k8s teardown-stack` SHALL list the same entries in `details.path_source_deletes`, in the order of the deletes.

#### Scenario: The dry run lists the objects of the build of a component
- **WHEN** the tree `<tmp>/env` holds the Application `logging` with the path source `env/logging`, `kubectl kustomize` of `<tmp>/env/logging` gives the NetworkPolicy `logging/loki-perimeter` and the NetworkPolicy `logging/default-deny` of the component, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** `details.path_sources` is one entry with the Application `logging`, the path `env/logging` and the two NetworkPolicies, and the command starts `kubectl kustomize` only as a local read

### Requirement: The deploy-stack dry run fetches no path source of another repository
For a path source of another repository, the dry run of `devops k8s deploy-stack` SHALL fetch nothing and build nothing. It SHALL list the fetch in `details.source_fetches`, and SHALL give `null` as the objects of the source in `details.path_sources`.

#### Scenario: The dry run lists the fetch of a path source
- **WHEN** the path source of the Application `logging` of the tree `<tmp>/env` is `k8s/logging` of `https://example.com/infra.git` at `v1.0.0`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** the entry of `details.path_sources` gives `null` as its objects, `details.source_fetches` lists the fetch of `https://example.com/infra` at `v1.0.0`, and the command starts no git fetch and no `kubectl kustomize`
