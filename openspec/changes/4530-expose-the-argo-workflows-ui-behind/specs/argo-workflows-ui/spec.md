## Purpose
The Argo Workflows server and its UI: the client auth mode, the read-only account, the Ingress host behind Cloudflare Access, the perimeter, and the Grafana links and dashboard of the controller metrics.

## ADDED Requirements

### Requirement: The Argo server runs in client auth mode with its own account
The Argo Workflows values in `k8s/argo-workflows/values.yaml` SHALL enable the chart's argo-server with one replica, `authMode: client`, ServiceAccount `argo-workflows-ui` and the argument `--configmap=argo-workflows-ui-links`, SHALL set the pod and container security context that Pod Security `restricted` requires, and MUST leave the chart's own Ingress disabled.

#### Scenario: The chart render of the server
- **WHEN** A person runs `uv run devops ci --check --only charts` over `k8s/argo-workflows/values.yaml` on a host that has helm and docker
- **THEN** The render holds Deployment `argo-server` with one replica, the arguments `--auth-mode=client` and `--configmap=argo-workflows-ui-links`, ServiceAccount `argo-workflows-ui`, and no Ingress

#### Scenario: The live server pod
- **WHEN** A person runs the live check `kubectl -n argo-workflows get deployment argo-server -o json` after the sync of `k8s/argo-workflows/values.yaml`
- **THEN** The container args hold `--auth-mode=client`, the pod runs as ServiceAccount `argo-workflows-ui`, and that account is not `argo-workflows-executor`

### Requirement: The UI account reads Workflows and their logs and writes nothing
Role `argo-workflows-ui` in `k8s/argo-workflows/rbac-ui.yaml` SHALL grant `get`, `list` and `watch` on `workflows`, `workflowtemplates`, `workflowtaskresults`, `pods` and `pods/log` in namespace `argo-workflows`, SHALL be bound to ServiceAccount `argo-workflows-ui`, and MUST grant no `create`, `update`, `patch` or `delete`.

#### Scenario: The write verbs are refused
- **WHEN** A person runs the live check `kubectl auth can-i create workflows.argoproj.io -n argo-workflows --as=system:serviceaccount:argo-workflows:argo-workflows-ui`, and again with `delete`, `update`, `patch` and `list`
- **THEN** The API server answers `no` to the four write verbs, and answers `yes` to `list`

#### Scenario: The rendered Role and its binding
- **WHEN** A person runs `uv run devops ci --check --only k8s` over `k8s/argo-workflows/rbac-ui.yaml`
- **THEN** The row passes, and the render holds Role `argo-workflows-ui` with a RoleBinding to ServiceAccount `argo-workflows-ui` in namespace `argo-workflows`

### Requirement: The UI host routes through the ingress Application
Ingress `argo-workflows-ui` in namespace `argo-workflows` in `k8s/ingress/ingress-routes.yaml` SHALL route host `workflows.example.com` on path `/` of type `Prefix` to Service `argo-server` port 2746, with class `traefik` and the entrypoint annotation `web`, and `devops k8s deploy-stack --stack infra` SHALL set the configured domain on that host.

#### Scenario: The live host and backend
- **WHEN** A person runs the live check `kubectl -n argo-workflows get ingress argo-workflows-ui -o jsonpath='{.spec.rules[0]}'` after a deploy of stack `infra`
- **THEN** It prints the configured domain under `workflows.`, the path `/`, and the backend Service `argo-server` on port 2746

#### Scenario: The Ingress in git
- **WHEN** A person runs `uv run devops ci --check --only k8s` over `k8s/ingress/ingress-routes.yaml`
- **THEN** The row passes, the file holds host `workflows.example.com` with the backend `argo-server` on port 2746, and every host of the file still holds the placeholder in git

### Requirement: The perimeter admits Traefik on the server port and nothing else
The ingress policy of namespace `argo-workflows` in `k8s/argo-workflows/networkpolicy.yaml` SHALL admit Traefik pods of namespace `kube-system` on TCP 2746 and the scrape of namespace `monitoring` on TCP 9090, and MUST admit no other ingress.

#### Scenario: The rendered perimeter
- **WHEN** A person runs `uv run devops ci --check --only k8s` over `k8s/argo-workflows/networkpolicy.yaml`
- **THEN** The row passes, and the ingress rules name only those two peers and those two ports

### Requirement: The UI links open a Workflow's logs in Grafana
ConfigMap `argo-workflows-ui-links` in namespace `argo-workflows` in `k8s/ingress/argo-workflows-ui-links.yaml` SHALL hold a `links` value with a workflow-scoped link to `https://grafana.example.com/explore` that selects the logs of namespace `argo-workflows` and the pods of `{{workflow.name}}` on the Loki datasource, and `devops k8s deploy-stack --stack infra` SHALL set the configured domain in that value.

#### Scenario: The live links value
- **WHEN** A person runs the live check `kubectl -n argo-workflows get configmap argo-workflows-ui-links -o jsonpath='{.data.links}'` after a deploy of stack `infra`
- **THEN** The value names `https://grafana.<configured domain>/explore`, and it holds no `example.com`

#### Scenario: A Workflow's logs are in Loki
- **WHEN** A person queries Loki with `uv run devops k8s logs --query` for the stream `{namespace="argo-workflows"}` after the version WorkflowTemplate ran
- **THEN** Loki answers with the lines of that Workflow's pods, and the link of the UI opens the same lines in Grafana Explore

### Requirement: The controller metrics reach the dashboard
The chart's ServiceMonitor SHALL stay enabled on port `9090` with `prometheusOperatorObjects` scraping namespace `argo-workflows`, and `k8s/monitoring/dashboards/kustomization.yaml` SHALL provision the community dashboard `argo-workflows.json` in ConfigMap `grafana-argo-workflows-dashboards` with a uid of its own.

#### Scenario: The dashboard lints
- **WHEN** A person runs `uv run devops grafana dashboards lint k8s/monitoring/dashboards` on `k8s/monitoring/dashboards/argo-workflows.json`
- **THEN** The command exits 0, reports no error, and no two dashboards share a uid

#### Scenario: The controller target is up
- **WHEN** A person runs the live check `uv run devops prometheus query 'up{namespace="argo-workflows"}'` on the cluster that runs `k8s/monitoring/k8s-monitoring-values.yaml`
- **THEN** The controller's target answers `1`

### Requirement: The k8s row passes over the new manifests
The change MUST pass the `k8s` row of `devops ci` over `k8s/argo-workflows/rbac-ui.yaml`, `k8s/argo-workflows/networkpolicy.yaml`, `k8s/ingress/ingress-routes.yaml` and `k8s/ingress/argo-workflows-ui-links.yaml`.

#### Scenario: The k8s row of the change
- **WHEN** A person runs `uv run devops ci --check --only k8s` over the new manifests
- **THEN** The row passes, and every host and every link in git holds the placeholder `example.com` only
