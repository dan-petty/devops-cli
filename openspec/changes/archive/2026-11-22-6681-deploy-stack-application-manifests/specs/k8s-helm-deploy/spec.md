## ADDED Requirements

### Requirement: deploy-stack applies the builds of the path sources of the Applications of each stack
`devops k8s deploy-stack` SHALL build each path source of each Argo CD Application that `APPLICATIONS_BY_STACK` names for a selected stack, with Kustomize. A source of the `origin` of the checkout of the tree SHALL read the checkout, and a source of another repository SHALL be fetched at its `targetRevision` before the deploy touches the cluster. The deploy SHALL apply each build that holds an object with `kubectl apply -f -` before the charts.

#### Scenario: The build of a path source with a component is applied before the charts
- **WHEN** the tree `<tmp>/env` holds the Application `logging` with the path source `env/logging`, whose kustomization takes the local component `env/components/perimeter`, `kubectl kustomize` of `<tmp>/env/logging` gives two NetworkPolicies, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --no-push-secrets` runs on a cluster without Argo CD
- **THEN** the deploy starts `kubectl apply -f -` with the build as input before the `helm upgrade` of release `loki`

### Requirement: deploy-stack stops when the cluster refuses a build
When `kubectl apply -f -` of a build exits with an error, `devops k8s deploy-stack` SHALL exit 1 with the reason of kubectl, and SHALL install no chart.

#### Scenario: A refused build stops the deploy before the charts
- **WHEN** the tree `<tmp>/env` holds the Application `logging` of the scenario above, kubectl refuses `kubectl apply -f -` with `admission denied`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --no-push-secrets` runs on a cluster without Argo CD
- **THEN** the command exits 1, prints `admission denied`, and starts no `helm upgrade`

### Requirement: teardown-stack deletes the builds of the path sources
`devops k8s teardown-stack` SHALL build the same path sources as `deploy-stack`, and SHALL delete each build that holds an object with `kubectl delete -f - --ignore-not-found`, in the reverse order of the deploy, before the manifest paths and the Helm uninstalls. When kubectl refuses a delete, the teardown SHALL print the reason and go on. When a build fails, the teardown SHALL exit 1 with the reason before it deletes an object or uninstalls a chart.

#### Scenario: The teardown deletes the build before the chart
- **WHEN** the tree `<tmp>/env` holds the Application `logging` of the scenario above, and `devops k8s teardown-stack --stack logging --k8s-dir <tmp>/env` runs on a cluster without Argo CD
- **THEN** the teardown starts `kubectl delete -f - --ignore-not-found` with the build as input before the `helm uninstall` of release `loki`

#### Scenario: A failed build stops the teardown
- **WHEN** the tree `<tmp>/env` holds the Application `logging` of the scenario above, `kubectl kustomize` of `<tmp>/env/logging` exits 1 with `missing resource`, and `devops k8s teardown-stack --stack logging --k8s-dir <tmp>/env` runs on a cluster without Argo CD
- **THEN** the command exits 1, prints `missing resource`, and starts no `kubectl delete` and no `helm` command

### Requirement: deploy-stack stops on an Application that the tree does not hold
When the tree holds no Application of a name that `APPLICATIONS_BY_STACK` gives for a selected stack, `devops k8s deploy-stack` and `devops k8s teardown-stack` SHALL exit 1 and name the Application before they touch the cluster.

#### Scenario: A tree with no Application of the table
- **WHEN** the tree `<tmp>/env` holds the Application `loki` and no Application `logging`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** the command exits 1 and names the Application `logging`

### Requirement: The deploy-stack dry run lists the objects of each build
The dry run of `devops k8s deploy-stack` SHALL build each path source of the checkout as a local read. It SHALL list in `details.path_sources`, in the order of the deploy, the key `<application>: <path>` of each build with its objects: `<kind> <namespace>/<name>`, or `<kind> <name>` for an object of the cluster scope. The dry run of `devops k8s teardown-stack` SHALL list the same entries in `details.path_source_deletes`, in the order of the deletes.

#### Scenario: The dry run lists the objects of the build of a component
- **WHEN** the tree `<tmp>/env` holds the Application `logging` with the path source `env/logging`, `kubectl kustomize` of `<tmp>/env/logging` gives the NetworkPolicy `logging/loki-perimeter` and the NetworkPolicy `logging/default-deny` of the component, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** `details.path_sources` is the one entry `logging: env/logging` with `NetworkPolicy logging/loki-perimeter` and `NetworkPolicy logging/default-deny`, and the command starts `kubectl kustomize` only as a local read

#### Scenario: The teardown dry run lists the builds in the order of the deletes
- **WHEN** the Application `logging` of the tree `<tmp>/env` has the path sources `env/logging` and `env/extra`, and `devops k8s deploy-stack` and `devops k8s teardown-stack` run with `--stack logging --k8s-dir <tmp>/env --dry-run`
- **THEN** `details.path_sources` gives `logging: env/logging` and then `logging: env/extra`, and `details.path_source_deletes` gives `logging: env/extra` and then `logging: env/logging`

### Requirement: The deploy-stack dry run fetches no path source of another repository
For a path source of another repository, the dry run of `devops k8s deploy-stack` SHALL fetch nothing and build nothing. It SHALL list the fetch in `details.source_fetches`, and SHALL give `null` as the objects of the source in `details.path_sources`.

#### Scenario: The dry run lists the fetch of a path source
- **WHEN** the path source of the Application `logging` of the tree `<tmp>/env` is `k8s/logging` of `https://example.com/infra.git` at `v1.0.0`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** the entry of `details.path_sources` gives `null` as its objects, `details.source_fetches` lists the fetch of `https://example.com/infra` at `v1.0.0`, and the command starts no git fetch and no `kubectl kustomize`

### Requirement: The stack dry runs build each folder with no route to the network
The dry runs of `devops k8s deploy-stack` and `devops k8s teardown-stack` SHALL start `kubectl kustomize` with no route to the network: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` and their lower-case names point to the closed port `127.0.0.1:9`, `NO_PROXY` and `no_proxy` are empty, and `GIT_ALLOW_PROTOCOL=file`, `GIT_SSH_COMMAND=false`, `GIT_TERMINAL_PROMPT=0` and `GIT_CONFIG_NOSYSTEM=1` keep git to local repositories. A real run SHALL use the normal environment.

#### Scenario: Only a dry-run build gets no route to the network
- **WHEN** the tree `<tmp>/env` holds the Application `logging` with the path source `env/logging`, and `devops k8s deploy-stack` and `devops k8s teardown-stack` run with `--stack logging --k8s-dir <tmp>/env`, first with `--dry-run` and then on a cluster without Argo CD
- **THEN** each dry run starts `kubectl kustomize` with the environment above, and each real run starts it with no environment of its own

#### Scenario: A remote target fails the dry-run build at once
- **WHEN** the kustomization of `env/logging` names a remote target at `192.0.2.1`: a remote base by an https URL, a `git::` URL, an ssh URL or the SCP form, a remote base by a path on `github.com`, the `path` of a PatchTransformer inline or in a local file of `transformers`, or a file or an env file with `?ref=main` of a ConfigMapGenerator, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs with the real `kubectl kustomize`
- **THEN** the build fails within 5 seconds with the `proxyconnect` error of Go or with a refused git transport, and the command exits 0, gives `null` as the objects of `logging: env/logging`, and lists `logging: env/logging` in `details.kustomize_fetches` with that error

#### Scenario: A folder with only local bases and components
- **WHEN** the path source `env/logging` takes only the local component `../components/perimeter`, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs
- **THEN** the command builds the folder with `kubectl kustomize` as a local read, and `details.kustomize_fetches` is empty

### Requirement: A URL of a loopback address stays a local read in the stack dry runs
Go sends a request to `localhost` or to a loopback address with no proxy (`golang.org/x/net/http/httpproxy`). So the environment of the dry-run builds SHALL NOT block a URL of a loopback address: such a URL is a local read of the host, and a dry run MAY load it.

#### Scenario: A file at a loopback address
- **WHEN** a server of the test at `127.0.0.1` gives the ConfigMap `loki-extra`, the kustomization of `env/logging` names its URL, and `devops k8s deploy-stack --stack logging --k8s-dir <tmp>/env --dry-run` runs with the real `kubectl kustomize`
- **THEN** the command exits 0, lists `ConfigMap loki-extra` as the objects of `logging: env/logging`, and `details.kustomize_fetches` is empty

### Requirement: The stack dry runs list a failed build and go on
When a build of a path source fails in the dry run of `devops k8s deploy-stack` or `devops k8s teardown-stack`, the dry run SHALL give `null` as its objects, SHALL list the key of the build in `details.kustomize_fetches` with the first line of the error of kubectl, and SHALL go on. The real run SHALL stop on a failed build, as before.

#### Scenario: A failed dry-run build is listed and the dry runs go on
- **WHEN** `kubectl kustomize` of `<tmp>/env/logging` exits 1 with a warning of Kustomize and then the error of kubectl, and `devops k8s deploy-stack` and `devops k8s teardown-stack` run with `--stack logging --k8s-dir <tmp>/env --dry-run`
- **THEN** both commands exit 0, give `null` as the objects of `logging: env/logging`, and list `logging: env/logging` in `details.kustomize_fetches` with the line of the error of kubectl
