# Tasks

## 1. Enable the Argo server in client auth mode

Kind: other. Reads: `k8s/argo-workflows/values.yaml`, `k8s/argo-workflows/kustomization.yaml`, `tests/k8s/test_k8s_argo_workflows.py`. Changes: `k8s/argo-workflows/values.yaml`, `tests/k8s/test_k8s_argo_workflows.py`.

- [ ] 1.1 In `k8s/argo-workflows/values.yaml`, replace the `server:` block that holds `enabled: false` with one that sets `enabled: true`, `replicas: 1`, `authMode: client`, `secure: false`, `serviceAccount: {create: true, name: argo-workflows-ui}`, `extraArgs: [--configmap=argo-workflows-ui-links]`, `ingress: {enabled: false}`, the pod and container security context that Pod Security `restricted` needs, and a 100m/128Mi request with a 500m/512Mi limit. In `tests/k8s/test_k8s_argo_workflows.py`, change `test_the_controller_runs_one_namespaced_replica_with_no_server_database_or_archive` to assert the new server block, and add the server pod and container contexts to `test_every_pod_the_namespace_admits_meets_restricted_pod_security`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argo_workflows.py` passes

## 2. Give the UI account read-only RBAC

Kind: manifest. Reads: `k8s/argo-workflows/kustomization.yaml`, `tests/gate/k8s_checks/argo_workflows.py`, `tests/commands/k8s/test_k8s.py`, `tests/k8s/test_k8s_argo_workflows.py`. Changes: `k8s/argo-workflows/rbac-ui.yaml` (new), `k8s/argo-workflows/kustomization.yaml`, `tests/k8s/test_k8s_argo_workflows.py`, `tests/gate/k8s_checks/argo_workflows.py`, `tests/commands/k8s/test_k8s.py`.

- [ ] 2.1 The failing case is the new `test_the_ui_account_reads_workflows_and_their_logs_and_writes_nothing` in `tests/k8s/test_k8s_argo_workflows.py`, which reads `k8s/argo-workflows/rbac-ui.yaml` and fails until Role `argo-workflows-ui` grants exactly `get`, `list` and `watch` on `workflows`, `workflowtemplates`, `workflowtaskresults`, `pods` and `pods/log`, grants no `create`, `update`, `patch` or `delete`, and its RoleBinding names ServiceAccount `argo-workflows-ui`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argo_workflows.py` fails on the base
- [ ] 2.2 Create `k8s/argo-workflows/rbac-ui.yaml` with Role `argo-workflows-ui` and its RoleBinding in namespace `argo-workflows`, and list the file in `k8s/argo-workflows/kustomization.yaml`. Add the Role and the RoleBinding to the expected list of `check_the_kustomization_renders_the_template_and_the_perimeter_and_nothing_else` in `tests/gate/k8s_checks/argo_workflows.py`, and update the case in `tests/commands/k8s/test_k8s.py` that lists the objects of the build of Application `argo-workflows-manifests`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argo_workflows.py` passes

## 3. Open only the server port in the perimeter

Kind: other. Reads: `k8s/argo-workflows/networkpolicy.yaml`, `k8s/gitea/networkpolicy.yaml`, `tests/k8s/test_k8s_argo_workflows.py`, `tests/gate/k8s_checks/network_policies.py`. Changes: `k8s/argo-workflows/networkpolicy.yaml`, `tests/k8s/test_k8s_argo_workflows.py`.

- [ ] 3.1 Add one ingress rule to the ingress policy of `k8s/argo-workflows/networkpolicy.yaml` that admits pods of namespace `kube-system` with the label `app.kubernetes.io/name: traefik` on TCP 2746, as `k8s/gitea/networkpolicy.yaml` selects them, beside the existing scrape of namespace `monitoring` on TCP 9090, and keep the egress rules unchanged. Extend `test_the_perimeter_admits_the_metrics_scrape_and_reaches_dns_and_the_api_server` in `tests/k8s/test_k8s_argo_workflows.py` to assert the two ingress rules and the two egress rules
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argo_workflows.py` passes

## 4. Route the UI host through the ingress Application

Kind: other. Reads: `k8s/ingress/ingress-routes.yaml`, `k8s/overlays/homelab/ingress/kustomization.yaml`, `k8s/argocd/apps/projects.yaml`, `tests/gate/k8s_checks/host_overrides.py`, `tests/k8s/test_k8s_argo_workflows.py`. Changes: `k8s/ingress/ingress-routes.yaml`, `k8s/argocd/apps/projects.yaml`, `tests/k8s/test_k8s_argo_workflows.py`.

- [ ] 4.1 Add Ingress `argo-workflows-ui` in namespace `argo-workflows` to `k8s/ingress/ingress-routes.yaml`: class `traefik`, the annotation `traefik.ingress.kubernetes.io/router.entrypoints: web`, one rule for host `workflows.example.com`, path `/` of type `Prefix`, backend Service `argo-server` port 2746, and no `tls` block. Add namespace `argo-workflows` to the destinations of AppProject `homelab-system` in `k8s/argocd/apps/projects.yaml`. Add the case `test_the_ui_ingress_routes_the_host_to_the_server_and_the_project_admits_its_namespace` to `tests/k8s/test_k8s_argo_workflows.py`, which reads both files and asserts the class, the annotation, the host, the path, the backend name and port, the absence of `tls`, and the destination
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_argo_workflows.py` passes

## 5. Create the links ConfigMap and its gate case

Kind: other. Reads: `k8s/ingress/kustomization.yaml`, `k8s/ingress/open-webui-origins.yaml`, `k8s/monitoring/grafana-values.yaml`, `tests/gate/k8s_checks/host_overrides.py`. Changes: `k8s/ingress/argo-workflows-ui-links.yaml` (new), `k8s/ingress/kustomization.yaml`, `tests/gate/k8s_checks/host_overrides.py`.

- [ ] 5.1 Create `k8s/ingress/argo-workflows-ui-links.yaml` with ConfigMap `argo-workflows-ui-links` in namespace `argo-workflows` and a `links` value that holds a workflow-scoped link to `https://grafana.example.com/explore` with the LogQL selector `{namespace="argo-workflows", pod=~"{{workflow.name}}-.*"}` on the Loki datasource, and list the file in `k8s/ingress/kustomization.yaml` beside `open-webui-origins.yaml`. Add the case `check_the_ui_links_open_the_workflow_logs_in_grafana` to `tests/gate/k8s_checks/host_overrides.py`, which builds the overlay of Application `ingress` with `host_patches` and fails until the ConfigMap data value holds `grafana.<domain>` and no placeholder
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 6. Update the tests that list the ingress build objects and patches

Kind: other. Reads: `tests/commands/k8s/test_k8s.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/k8s/test_k8s_argocd_gate.py`, `tests/k8s/test_k8s_template.py`, `k8s/ingress/argo-workflows-ui-links.yaml`. Changes: `tests/commands/k8s/test_k8s.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/k8s/test_k8s_argocd_gate.py`, `tests/k8s/test_k8s_template.py`.

- [ ] 6.1 Update the cases that list the objects and the patches of the build of Application `ingress` now that it renders the second ConfigMap: `test_deploy_stack_on_argo_cd_sets_the_open_webui_origins_under_the_configured_domain` in `tests/commands/k8s/test_k8s.py`, which must select the `open-webui-origins` patch by its target name instead of the first ConfigMap patch, and the object lists of `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/k8s/test_k8s_argocd_gate.py` and `tests/k8s/test_k8s_template.py`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` passes

## 7. Provision the Argo Workflows dashboard

Kind: manifest. Reads: `k8s/monitoring/dashboards/kustomization.yaml`, `k8s/monitoring/dashboards/seaweedfs.json`, `k8s/monitoring/k8s-monitoring-values.yaml`, `tests/prometheus/test_k8s_monitoring_dashboards.py`. Changes: `k8s/monitoring/dashboards/argo-workflows.json` (new), `k8s/monitoring/dashboards/kustomization.yaml`, `tests/prometheus/test_k8s_monitoring_dashboards.py`.

- [ ] 7.1 The failing case is the new `test_the_argo_workflows_dashboard_is_provisioned` in `tests/prometheus/test_k8s_monitoring_dashboards.py`, which fails until `k8s/monitoring/dashboards/kustomization.yaml` lists a generator for `k8s/monitoring/dashboards/argo-workflows.json` in ConfigMap `grafana-argo-workflows-dashboards` with uid `argo-workflows`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` fails on the base
- [ ] 7.2 Copy the Argo Workflows dashboard of adinhodovic/argo-workflows-mixin (Apache-2.0) at a pinned commit to `k8s/monitoring/dashboards/argo-workflows.json`, with uid `argo-workflows`, one-space indentation, a datasource object in place of each `$DS_PROMETHEUS` text, and no empty query, so `uv run devops grafana dashboards lint k8s/monitoring/dashboards` exits 0. Add the configMapGenerator `grafana-argo-workflows-dashboards` for the file to `k8s/monitoring/dashboards/kustomization.yaml`, beside `grafana-database-dashboards`, and add the case to `tests/prometheus/test_k8s_monitoring_dashboards.py`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py` passes

## 8. Document the UI host, the account, the links and the dashboard

Kind: other. Reads: `k8s/README.md`, `k8s/argo-workflows/values.yaml`, `k8s/ingress/ingress-routes.yaml`, `k8s/ingress/argo-workflows-ui-links.yaml`. Changes: `k8s/README.md`.

- [ ] 8.1 In the Argo Workflows section of `k8s/README.md`, replace the sentence that says the install has no argo-server with the server, the `client` auth mode, the read-only account and the command `kubectl create token argo-workflows-ui -n argo-workflows`. Add the UI host to the access table, the UI Ingress and the links ConfigMap to the tree listing, and `argo-workflows.json` with its source and the changes the copy carries to Grafana Dashboards. Add the live checks of the read-only account, the Ingress backend, the links value and the LogQL query of a Workflow's logs to the install check block
  - Verification: `$ uv run devops ci docs` passes
- [ ] 8.2 Edit `k8s/README.md`: the Argo Workflows section, the access table, the Grafana Dashboards section and the live check block
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 4: The Argo UI loads at its host through Access and lists the Workflows of the managed namespaces; the UI account cannot submit, delete or resubmit (an RBAC test or a `kubectl auth can-i` check in the PR comment).
- Group 5: Workflow pod logs of a test Workflow appear in Loki, and the UI link opens them in Grafana.
- Group 7: The controller metrics show in Prometheus, and the Argo Workflows dashboard renders in Grafana.
- Group 5: No private hostname in git; the rendered manifests pass the k8s row of `devops ci`.
