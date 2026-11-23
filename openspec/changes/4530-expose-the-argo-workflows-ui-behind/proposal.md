# Proposal

## Why

The Argo Workflows controller runs in namespace `argo-workflows`, and no Argo server or UI is reachable, so a person cannot see Workflow runs, their steps, their logs or a failed node without `kubectl` (#4530). The owner decided on 2026-11-11 to expose the UI. This change enables the chart's argo-server in client auth mode with a read-only account, routes its host through the ingress Application behind Cloudflare Access, links a Workflow to its logs in Grafana Explore, and provisions the controller-metrics dashboard.

## What Changes

- Enable the chart's argo-server in `k8s/argo-workflows/values.yaml` with one replica, `authMode: client`, ServiceAccount `argo-workflows-ui`, the `--configmap=argo-workflows-ui-links` argument, the security context that Pod Security `restricted` needs, and the chart's own Ingress off.
- Add Role `argo-workflows-ui` and its RoleBinding in `k8s/argo-workflows/rbac-ui.yaml` with only `get`, `list` and `watch` on Workflows, WorkflowTemplates, WorkflowTaskResults, pods and pod logs, and list the file in `k8s/argo-workflows/kustomization.yaml`.
- Admit Traefik pods of namespace `kube-system` on TCP 2746 in `k8s/argo-workflows/networkpolicy.yaml`, beside the existing scrape of namespace `monitoring` on TCP 9090.
- Add Ingress `argo-workflows-ui` for host `workflows.example.com` to `k8s/ingress/ingress-routes.yaml`, and namespace `argo-workflows` to the destinations of AppProject `homelab-system` in `k8s/argocd/apps/projects.yaml`.
- Add ConfigMap `argo-workflows-ui-links` in `k8s/ingress/argo-workflows-ui-links.yaml`, whose `links` value opens a Workflow's logs in Grafana Explore under `grafana.example.com`, and list it in `k8s/ingress/kustomization.yaml`.
- Provision the community Argo Workflows dashboard as `k8s/monitoring/dashboards/argo-workflows.json` in ConfigMap `grafana-argo-workflows-dashboards` through `k8s/monitoring/dashboards/kustomization.yaml`.
- Document the UI host, the read-only account, the token command, the Grafana links and the dashboard in `k8s/README.md`.
- The read-only grant in namespace `devops` and the start page link wait for the items that own them, so this change adds neither.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `argo-workflows-ui`: The Argo server runs in client auth mode with its own account, The UI account reads Workflows and their logs and writes nothing, The UI host routes through the ingress Application, The perimeter admits Traefik on the server port and nothing else, The UI links open a Workflow's logs in Grafana, The controller metrics reach the dashboard, The k8s row passes over the new manifests

### Modified Capabilities

- `homelab-project-destinations`: The homelab-system project admits the argo-workflows namespace

## Impact

- Code: `k8s/argo-workflows/values.yaml`, `k8s/argo-workflows/rbac-ui.yaml`, `k8s/argo-workflows/kustomization.yaml`, `k8s/argo-workflows/networkpolicy.yaml`, `k8s/ingress/ingress-routes.yaml`, `k8s/argocd/apps/projects.yaml`, `k8s/ingress/argo-workflows-ui-links.yaml`, `k8s/ingress/kustomization.yaml`, `k8s/monitoring/dashboards/argo-workflows.json`, `k8s/monitoring/dashboards/kustomization.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/k8s/test_k8s_argo_workflows.py`, `tests/gate/k8s_checks/argo_workflows.py`, `tests/commands/k8s/test_k8s.py`, `tests/gate/k8s_checks/host_overrides.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/k8s/test_k8s_argocd_gate.py`, `tests/k8s/test_k8s_template.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`

## Feasibility

- The premise is confirmed: the probes say "The path `k8s/argo-workflows/values.yaml` is a file of the staging commit." and `read_file` of it showed `k8s/argo-workflows/values.yaml:29:enabled: false` under the `server:` key, so the chart renders no argo-server and no UI is reachable.
- `read_file` of `k8s/argo-workflows/kustomization.yaml` showed `k8s/argo-workflows/kustomization.yaml:5:- networkpolicy.yaml` and `k8s/argo-workflows/kustomization.yaml:6:- workflowtemplate-version.yaml`, so the directory renders no Role, no Ingress and no links ConfigMap today.
- `read_file` of `k8s/argo-workflows/networkpolicy.yaml` showed one ingress rule only, with the peer `k8s/argo-workflows/networkpolicy.yaml:20:kubernetes.io/metadata.name: monitoring` and port 9090, so the perimeter admits no Traefik pod today and the plan adds exactly one rule.
- `read_file` of `k8s/ingress/ingress-routes.yaml` showed the host pattern `k8s/ingress/ingress-routes.yaml:59:- host: ai.example.com` with the annotation `k8s/ingress/ingress-routes.yaml:21:traefik.ingress.kubernetes.io/router.entrypoints: web`, so the UI host belongs in that file with that annotation.
- `read_file` of `k8s/argocd/apps/projects.yaml` showed `k8s/argocd/apps/projects.yaml:165:name: homelab-system`, its `k8s/argocd/apps/projects.yaml:187:destinations:` with 14 entries, the last being `k8s/argocd/apps/projects.yaml:215:namespace: cert-manager`, and no `argo-workflows`, so the project needs that entry for Application `ingress`.
- `read_file` of `k8s/argocd/apps/ingress.yaml` showed the Application renders `k8s/overlays/homelab/ingress`, and `read_file` of `k8s/overlays/homelab/ingress/kustomization.yaml` showed it includes `../../../ingress`, so a file listed in `k8s/ingress/kustomization.yaml` is rendered by Application `ingress` and patched at deploy time.
- The staged constants that the plan relies on: `src/devops_cli/config/constants.py:1200:CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER: Final[str] = "example.com"` gives the placeholder host, and `src/devops_cli/config/constants.py:1239:"infra": ("ingress",)` makes stack `infra` the stack whose deploy sets the configured domain on Application `ingress`.
- `src/devops_cli/k8s/argocd_overrides.py:152:if doc.get("kind") == "ConfigMap":` sends a ConfigMap to the data-value branch, and `src/devops_cli/k8s/argocd_overrides.py:143:if isinstance(value, str) and holds_template_domain_value(value)` keeps each `data` value that holds the placeholder, so a ConfigMap data value under the configured domain gets the patch. `k8s/ingress/open-webui-origins.yaml:20:CORS_ALLOW_ORIGIN: "https://chat.example.com;https://homelab.example.com"` is the committed precedent of a host value in that folder, listed by `k8s/ingress/kustomization.yaml:6:- open-webui-origins.yaml`.
- The links cannot live in the chart: `read_file` of `k8s/argocd/apps/argo-workflows.yaml` showed `k8s/argocd/apps/argo-workflows.yaml:10:sources:`, and `src/devops_cli/k8s/argocd_overrides.py:53:if spec.get("sources"):` guards a raise for an Application that renders several sources, so deploy-stack never patches that Application and the plan puts the links ConfigMap in Application `ingress`.
- `read_file` of `k8s/argo-workflows/values.yaml` showed `k8s/argo-workflows/values.yaml:25:singleNamespace: true`, so the controller watches only its own namespace and the read-only Role stays in `argo-workflows`.
- The log collection needs no change: `k8s/monitoring/k8s-monitoring-values.yaml:119:podLogsViaLoki:` is on with no namespace filter, and the Loki datasource is `k8s/monitoring/grafana-values.yaml:156:uid: loki`, which the link names.
- The cases that pin the changed files: `tests/k8s/test_k8s_argo_workflows.py:def test_the_controller_runs_one_namespaced_replica_with_no_server_database_or_archive`, `tests/k8s/test_k8s_argo_workflows.py:def test_every_pod_the_namespace_admits_meets_restricted_pod_security`, `tests/k8s/test_k8s_argo_workflows.py:def test_the_perimeter_admits_the_metrics_scrape_and_reaches_dns_and_the_api_server`, `tests/gate/k8s_checks/argo_workflows.py:def check_the_kustomization_renders_the_template_and_the_perimeter_and_nothing_else`, `tests/gate/k8s_checks/host_overrides.py:def check_kustomize_applies_the_overrides_to_every_host_the_application_renders` and `tests/gate/k8s_checks/argocd_apps.py:def check_appproject_trial_and_orphans`, which asserts that no destination of `homelab-system` names `trial` and so passes with the new entry.
- `read_file` of `tests/gate/k8s_checks/host_overrides.py` showed `tests/gate/k8s_checks/host_overrides.py:29:if doc.get("kind") == "Ingress":` in `_document_hosts`, which counts Ingress, IngressRoute and Mattermost hosts only, so the links value of a ConfigMap needs its own case and the host count of the existing case stays true.
- `read_file` of `k8s/monitoring/dashboards/kustomization.yaml` showed `k8s/monitoring/dashboards/kustomization.yaml:58:- name: grafana-database-dashboards`, the copy pattern of an upstream dashboard that this change follows, and the k8s row measures every generator, so the new ConfigMap needs no change to that measurement.
- The probes say "The path `workflows.example.com` is no file of the staging commit. No commit in the history deleted or renamed it.", so the UI host is a name that this change creates, and no commit removed it; the probes say "The path `k8s/README.md` is a file of the staging commit.", so the document group edits an existing file. The probe list names `k8s/ingress/ingress-routes.yaml` as not probed, and `read_file` read it.
- Group 2 verifies with `uv run devops ci test tests/k8s/test_k8s_argo_workflows.py`, whose new case `test_the_ui_account_reads_workflows_and_their_logs_and_writes_nothing` reads the verbs and the resources of `k8s/argo-workflows/rbac-ui.yaml`, so a Role that grants `create` or `delete` fails the group.
- Group 4 verifies with the same test module, whose new case `test_the_ui_ingress_routes_the_host_to_the_server_and_the_project_admits_its_namespace` reads the backend Service name and port of Ingress `argo-workflows-ui`, so a wrong Service name or port fails the group.
- The first checks against the real system: `uv run devops ci test tests/k8s/test_k8s_argo_workflows.py` fails on the base at the server assertion, `uv run devops ci --check --only k8s` fails on the base at the render list once the Role exists, `uv run devops grafana dashboards lint k8s/monitoring/dashboards` fails on the copied dashboard before its uid and datasource change, and `uv run devops ci docs` fails on the base at the new table row.
- The live checks run after the sync: `kubectl -n argo-workflows get deployment argo-server -o jsonpath='{.spec.template.spec.containers[0].args}'`, `kubectl auth can-i create workflows.argoproj.io -n argo-workflows --as=system:serviceaccount:argo-workflows:argo-workflows-ui`, `kubectl -n argo-workflows get ingress argo-workflows-ui -o jsonpath='{.spec.rules[0].http.paths[0].backend.service}'`, `kubectl -n argo-workflows get configmap argo-workflows-ui-links -o jsonpath='{.data.links}'`, `kubectl -n argocd get appproject homelab-system -o jsonpath='{.spec.destinations[*].namespace}'` and `uv run devops prometheus query 'up{namespace="argo-workflows"}'`.
- Runner capability: `uv run devops ci test` runs `pytest` from the image with failure class `test`; `uv run devops ci --check --only k8s` runs `kubectl` and the Python case files from the image with failure class `test`; `uv run devops ci docs` and `uv run devops grafana dashboards lint` run `devops` from the image with failure class `test`; the pod keeps readOnlyRootFilesystem true, runAsNonRoot true, capabilities.drop ALL and allowPrivilegeEscalation false.
- `uv run devops ci --check --only charts` needs `helm` and `docker`, both `NOT_IN_RUNNER` because the image holds no container engine, so only a person runs it and no `verify` of a group names it; the chart-render scenario names it as the render of the values file.
- The plan calls no function. The commands `uv run devops ci test`, `uv run devops ci --check --only k8s` and `uv run devops ci docs` need a checkout of the repository and no client and no network. Each live check needs a client of the cluster or of Prometheus and a network, so a person runs it on the workstation; the runner pod holds no cluster token.
- The pull requests that shared `k8s/README.md` (#6811 and #6816) merged into main.

## Existing Tool Considered

The argo-server of the Argo Workflows chart that the cluster already installs (chart 2.0.18, app v4.1.6) covers the UI, the client auth mode and the per-account RBAC, and the community dashboard adinhodovic/argo-workflows-mixin (Apache-2.0) covers the controller metrics. The change writes manifests, RBAC, one ConfigMap, one dashboard copy and one document, and builds no code.

## Dependencies

None.
