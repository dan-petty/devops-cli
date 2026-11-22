# Tasks

## 1. Add the SearXNG metrics-auth Secret row and its README rows

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `tests/invariants/test_k8s_searxng.py`, `tests/invariants/test_k8s_manifests.py`, `k8s/README.md`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_gitea.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/commands/test_config_commands.py`, `tests/invariants/test_k8s_renovate.py`, `tests/k8s/test_cluster_secret_key_refs.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_grafana_renderer_optional.py`, `tests/k8s/test_roadmap_service_key.py`. Changes: `src/devops_cli/k8s/cluster_secrets.py`, `tests/invariants/test_k8s_searxng.py`, `tests/invariants/test_k8s_manifests.py`, `k8s/README.md`.
Adds: `SEARXNG_METRICS_AUTH_KEY`

- [x] 1.1 `tests/invariants/test_k8s_searxng.py::test_the_metrics_secret_row` fails first: `CLUSTER_SECRETS` holds no row `devops/searxng-metrics-auth`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py tests/invariants/test_k8s_manifests.py` fails on the base
- [x] 1.2 Add `SEARXNG_METRICS_AUTH_KEY = "searxng_metrics_password"` beside `SEARXNG_SERVER_KEY` in `src/devops_cli/k8s/cluster_secrets.py`, and the row `devops/searxng-metrics-auth` of stack `devops` with `secret_type=_BASIC_AUTH_SECRET_TYPE`, entry `username` from `LiteralSource("searxng")`, entry `password` from `KeyringSource(SEARXNG_METRICS_AUTH_KEY)` and `restarts` of `deployment/searxng`. Write the failing case `test_the_metrics_secret_row` in `tests/invariants/test_k8s_searxng.py`, add the key to the expected keyring-only set of `test_keyring_sources_are_managed_keys_or_declared_keyring_only` in `tests/invariants/test_k8s_manifests.py`, and add to `k8s/README.md` the rows that `test_readme_lists_the_table` computes for the two new entries
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py tests/invariants/test_k8s_manifests.py` passes
- [x] 1.3 Edit `k8s/README.md` to add the Cluster Secrets rows of `devops/searxng-metrics-auth`
  - Verification: `$ uv run devops ci docs` passes

## 2. Follow the new Secret row in the push, plan and dry-run tests

Kind: other. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/commands/k8s/test_k8s.py`. Changes: `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/commands/k8s/test_k8s.py`.

- [x] 2.1 Add the value `searxng_metrics_password` to `FULL_KEYRING` in `tests/k8s/test_cluster_secret_push.py` and to the expected reads of `test_stack_devops_reads_the_app_key_gateway_key_and_webhook_secrets_and_runs_no_gh`; add the same value to `FULL_KEYRING` in `tests/k8s/test_cluster_secret_plan.py` and the new row to the expected rows of `test_table_holds_each_secret_entry_with_its_source_and_restarts`; and extend `test_deploy_stack_dry_run_lists_the_secrets_and_key_names_and_runs_nothing` in `tests/commands/k8s/test_k8s.py` with the line that the dry run prints for Secret `devops/searxng-metrics-auth`, naming keys `username` and `password` and holding no value
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_push.py tests/k8s/test_cluster_secret_plan.py tests/commands/k8s/test_k8s.py` passes

## 3. Set the OpenMetrics password placeholder in the settings

Kind: other. Reads: `k8s/devops/searxng/configmap.yaml`. Changes: `k8s/devops/searxng/configmap.yaml`.

- [x] 3.1 Add a `general` block to the `settings.yml` text of `k8s/devops/searxng/configmap.yaml` with `open_metrics: ${SEARXNG_METRICS_PASSWORD}` and a comment that the `render-settings` init container writes the password at pod start, and add no retry key, no password and no engine name to the settings
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 4. Render the settings at pod start

Kind: other. Reads: `k8s/devops/searxng/configmap.yaml`, `k8s/devops/searxng/deployment.yaml`, `tests/k8s/test_image_pins.py`. Changes: `k8s/devops/searxng/deployment.yaml`, `tests/k8s/test_image_pins.py`.

- [x] 4.1 Add an init container `render-settings` to `k8s/devops/searxng/deployment.yaml` that runs the image of the `searxng` container with `sh -c`, mounts ConfigMap `searxng-settings` read-only at `/etc/searxng-template` and a new `settings-rendered` `emptyDir` at `/etc/searxng-rendered`, writes `/etc/searxng-rendered/settings.yml` with `${SEARXNG_METRICS_PASSWORD}` replaced by the value of key `password` of Secret `searxng-metrics-auth`, declares its requests and limits, and sets `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` and `capabilities.drop: [ALL]`. The `searxng` container mounts the `settings-rendered` `emptyDir` at `/etc/searxng/settings.yml` with `subPath: settings.yml` in place of the `settings` ConfigMap mount, and the `settings` volume stays for the init container
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 5. Create the SearXNG ServiceMonitor and apply it after the Helm releases

Kind: behavior. Reads: `k8s/llm/gateway/servicemonitor.yaml`, `k8s/llm/kustomization.yaml`, `k8s/devops/searxng/service.yaml`, `k8s/devops/searxng/kustomization.yaml`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/invariants/test_architectural_invariants.py`, `tests/gate/k8s_checks/deploy_stack.py`, `tests/support/k8s_tree.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/ai/test_llm_pool_metrics.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_networking.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `tests/commands/k8s/test_subsystem_containment_and_redaction.py`, `tests/commands/test_k8s_manifest_dry_run.py`, `tests/k8s/test_image_pins.py`. Changes: `k8s/devops/searxng/servicemonitor.yaml` (new), `k8s/devops/searxng/kustomization.yaml`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/k8s/test_image_pins.py`.

- [x] 5.1 `tests/commands/k8s/test_k8s_devops_stack.py::test_the_devops_stack_applies_the_searxng_service_monitor` fails first: `PRODUCT_POST_HELM_BY_STACK["devops"]` holds no entry for `Path("searxng", "servicemonitor.yaml")`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_devops_stack.py tests/invariants/test_architectural_invariants.py` fails on the base
- [x] 5.2 Create `k8s/devops/searxng/servicemonitor.yaml` as a ServiceMonitor named `searxng` in namespace `devops` with the labels `app.kubernetes.io/name: searxng` and `app.kubernetes.io/part-of: devops-cli-stack`, a selector of `app.kubernetes.io/name: searxng`, and one endpoint on port `http` at `/metrics` every 15 s with `basicAuth` from keys `username` and `password` of Secret `searxng-metrics-auth`. Add it to the resources of `k8s/devops/searxng/kustomization.yaml`, add `Path("searxng", "servicemonitor.yaml")` to `PRODUCT_POST_HELM_BY_STACK` in `src/devops_cli/commands/k8s/stack_lifecycle.py` and to no pre-Helm table, and write `test_the_devops_stack_applies_the_searxng_service_monitor` in `tests/commands/k8s/test_k8s_devops_stack.py` to assert the post-Helm entry and its absence from `PRODUCT_MANIFESTS_BY_STACK`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_devops_stack.py tests/invariants/test_architectural_invariants.py` passes

## 6. Admit the monitoring namespace in the SearXNG ingress

Kind: other. Reads: `k8s/devops/searxng/networkpolicy.yaml`, `tests/gate/k8s_checks/network_policies.py`. Changes: `k8s/devops/searxng/networkpolicy.yaml`, `tests/gate/k8s_checks/network_policies.py`.

- [x] 6.1 Add one ingress rule to `searxng-perimeter-ingress` in `k8s/devops/searxng/networkpolicy.yaml` that selects the `monitoring` namespace by `kubernetes.io/metadata.name` on TCP port 8080 and carries no pod selector, and keep the two pod selector peers in the rule that holds them. Change `_admits` in `tests/gate/k8s_checks/network_policies.py` to skip a peer whose `namespaceSelector` names a namespace other than `devops`, so `check_the_service_and_the_stage_job_reach_searxng_and_the_runner_job_does_not` still holds that the runner Job pod reaches no SearXNG port
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 7. Admit the scrape in the monitoring egress

Kind: other. Reads: `k8s/monitoring/networkpolicy.yaml`, `tests/commands/test_review_rules_pack.py`, `tests/k8s/test_k8s_argo_workflows.py`, `tests/security/test_review_score.py`, `tests/server/routes/test_k8s_roadmap_service.py`. Changes: `k8s/monitoring/networkpolicy.yaml`, `tests/commands/test_review_rules_pack.py`, `tests/k8s/test_k8s_argo_workflows.py`, `tests/security/test_review_score.py`, `tests/server/routes/test_k8s_roadmap_service.py`.

- [x] 7.1 Add TCP port 8080 to the `devops` namespace peer of `monitoring-default-perimeter-egress` in `k8s/monitoring/networkpolicy.yaml`, beside port 8000, and change no other peer and no other policy
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 8. Document the metrics endpoint, the render and the two perimeters

Kind: other. Reads: `docs/CLUSTER.md`, `k8s/devops/searxng/deployment.yaml`, `k8s/devops/searxng/networkpolicy.yaml`, `k8s/devops/searxng/servicemonitor.yaml`. Changes: `docs/CLUSTER.md`.

- [x] 8.1 Extend the SearXNG section of `docs/CLUSTER.md` with the `general.open_metrics` placeholder, the `render-settings` init container, the ServiceMonitor that scrapes `/metrics` on port 8080 with basic auth from Secret `searxng-metrics-auth` after the Helm releases, and the two perimeters that admit the scrape
  - Verification: `$ uv run devops ci docs` passes
- [x] 8.2 Edit `docs/CLUSTER.md` for the placeholder, the render, the scrape and the two perimeters
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: The issue holds the query rate for each backend and the share of each `result`, over at least 3 days, split into Service traffic and check or manual traffic., The rate needs at least 3 days of real traffic after this scrape is live, and #6753 reads the series and writes the numbers.
- Pending person: The issue names the cause: the query rate or the cluster egress address., The cause follows from the series that #6753 reads and from a person's query from another egress address, so no code change delivers it.
- Pending person: A test over the `searxng-settings` ConfigMap holds the engine set that the measure chooses, and the test fails before the change., The project forbids a test that asserts a value of a manifest, and the engine set is chosen by #5595 from the measure; `devops k8s searxng-check` holds the engine set on the running service instead.
- Pending person: A `devops k8s searxng-check` run gets at least one hit for the `general` category., The run needs the live cluster and the rolled-out pod, and a person runs it after the merge.
- Group 3: The settings add no retry loop (#4094).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
