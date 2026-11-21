# Tasks

## 1. The Secrets of the store have ClusterSecret rows

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/invariants/test_k8s_manifests.py`. Changes: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/invariants/test_k8s_manifests.py`, `k8s/README.md`.

- [x] 1.1 Add the rows `object-store/seaweedfs-admin` and `object-store/seaweedfs-s3` to the expected table of `test_table_holds_each_secret_entry_with_its_source_and_restarts`, write `test_the_object_store_admin_password_is_generated_and_the_s3_identities_file_is_empty`, and add the key `seaweedfs_admin_password` to the keyring-only keys of `test_keyring_sources_are_managed_keys_or_declared_keyring_only`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/invariants/test_k8s_manifests.py` fails
- [x] 1.2 Add the two rows, `SEAWEEDFS_ADMIN_AUTH_KEY` and `SEAWEEDFS_S3_NO_IDENTITIES` to `src/devops_cli/k8s/cluster_secrets.py`, and the rows and their note to the Cluster Secrets section of `k8s/README.md`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/invariants/test_k8s_manifests.py` passes

## 2. deploy-stack installs the store with stack infra

Kind: behavior. Reads: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/commands/k8s/test_k8s.py`. Changes: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/commands/k8s/test_k8s.py`.

- [x] 2.1 Write `test_deploy_stack_installs_the_object_store_operator_after_cert_manager_and_the_store_last` in `tests/commands/k8s/test_k8s.py`, and add the store to the expected Secrets, kustomizations and post-Helm paths of the infra dry-run tests
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` fails
- [x] 2.2 Add the repository `seaweedfs-operator`, the release `seaweedfs-operator` after `plugin-barman-cloud`, and the post-Helm path `object-store` to stack `infra`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` passes

## 3. The k8s row checks the object store

Kind: manifest. Reads: `tests/gate/k8s_render.py`, `tests/gate/k8s_checks/argocd_apps.py`, `tests/gate/k8s_checks/job_admission_policy.py`, `src/devops_cli/k8s/cluster_secrets.py`. Changes: `tests/gate/k8s_checks/object_store.py` (new), `tests/gate/k8s_checks/argocd_apps.py`, `k8s/namespaces.yaml`, `k8s/argocd/apps/projects.yaml`, `k8s/argocd/apps/seaweedfs-operator.yaml` (new), `k8s/argocd/apps/object-store.yaml` (new), `k8s/object-store/` (new).

- [x] 3.1 Write `tests/gate/k8s_checks/object_store.py`: one function for each rule of the spec that returns its problems, one check that applies it to the committed render, and one that applies it to a fixture that breaks it. Add the kind `Seaweed` to the data safety check of `tests/gate/k8s_checks/argocd_apps.py`. The checks fail on the base tree, which has no store
  - Verification: `$ uv run devops ci --check --only k8s` fails and names `object_store`
- [x] 3.2 Add namespace `object-store`, the Applications `seaweedfs-operator` and `object-store`, the AppProject entries, and `k8s/object-store/kustomization.yaml`, `seaweed.yaml`, `networkpolicy.yaml`, `poddisruptionbudgets.yaml` and `operator-values.yaml`
  - Verification: `$ uv run devops ci --check --only k8s` passes, and `$ uv run devops k8s lint` finds no problem

## 4. The store alerts and has a dashboard

Kind: manifest. Reads: `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/networkpolicy.yaml`, `src/devops_cli/config/defaults.py`, `k8s/monitoring/dashboards/kustomization.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/seaweedfs.json` (new), `k8s/monitoring/dashboards/kustomization.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/monitoring/networkpolicy.yaml`, `tests/gate/k8s_checks/object_store.py`, `src/devops_cli/config/defaults.py`, `docs/CONFIGURATION.md`, `k8s/README.md`.

- [x] 4.1 Add the `seaweedfs` group of five alerts, the four SeaweedFS series to `SERVED_SERIES`, the dashboard of tag 4.54 with the lint changes, and its ConfigMap `grafana-storage-dashboards`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py tests/prometheus/test_k8s_monitoring_dashboards.py` passes, `$ uv run devops grafana dashboards lint k8s/monitoring/dashboards/seaweedfs.json` finds no problem, and `$ uv run devops ci --check --only k8s` passes
- [x] 4.2 Write the scrape rule of `tests/gate/k8s_checks/object_store.py`, which joins the egress of the `monitoring` policies and the ingress of the store for the `alloy-metrics` pod, then add the egress rule of `monitoring-default-perimeter` to namespace `object-store` on 9327 and the ServiceMonitors of the operator to the Alloy targets of the README section `Scrape Ownership`
  - Verification: `check_alloy_reaches_the_metrics_port_of_each_component` fails before the egress rule and `$ uv run devops ci --check --only k8s` passes after it
- [x] 4.3 Add `object-store` to `DEFAULT_ROADMAP_PROJECT_REVIEW_NAMESPACES`, so the project review reads the workloads of the store, and generate `docs/CONFIGURATION.md`
  - Verification: the names of `DEFAULT_ROADMAP_PROJECT_REVIEW_NAMESPACES` equal the names of the objects of `kind: Namespace` in `k8s/namespaces.yaml`, and `$ uv run devops ci docs` passes

## 5. The build test

Kind: other. Changes: `k8s/object-store/build-test/` (new).

- [x] 5.1 Add the kustomization of namespace `object-store-build-test` with the label `backup-client: "true"`, the ConfigMap of the boto3 and minio-go programs, and the two Jobs, each with a restricted security context and a digest-pinned image
  - Verification: `$ kubectl kustomize k8s/object-store/build-test` renders the namespace, the ConfigMap and the two Jobs, and `$ uv run devops k8s image-pins k8s/object-store/build-test` resolves both images

## 6. Documents

Kind: other. Changes: `k8s/README.md`, `k8s/catalog.toml`, `docs/adr/0034-the-object-store-is-seaweedfs-with-its-operator.md` (new), `docs/adr/README.md`.

- [x] 6.1 Add ADR 0034 and its index row, the catalog entry `object-store`, the README section `Object Store` (what runs where, versions, security, clients, rollout, build test, node restore), the alert rows, the dashboard rows, the scrape row and the folder tree
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- The general settings of the operator move to dan-petty/infra with the four-homes work of #6674; this change keeps them in `k8s/object-store/operator-values.yaml`.
- Pending a person: run `uv run devops k8s push-secrets --only object-store/seaweedfs-admin --only object-store/seaweedfs-s3` after the merge, then the same command with `--plan` until each key shows `unchanged`.
- Pending a person: run the steps of the README section `Build test` and post the results on the issue.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
