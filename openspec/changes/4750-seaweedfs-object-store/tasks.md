# Tasks

## 1. The k8s row checks the object store

Kind: manifest. Reads: `tests/gate/k8s_render.py`, `tests/gate/k8s_checks/argocd_apps.py`, `tests/gate/k8s_checks/job_admission_policy.py`, `src/devops_cli/k8s/cluster_secrets.py`. Changes: `tests/gate/k8s_checks/object_store.py` (new), `tests/gate/k8s_checks/argocd_apps.py`, `k8s/namespaces.yaml`, `k8s/argocd/apps/projects.yaml`, `k8s/argocd/apps/seaweedfs-operator.yaml` (new), `k8s/argocd/apps/object-store.yaml` (new), `k8s/object-store/` (new).

- [ ] 1.1 Write `tests/gate/k8s_checks/object_store.py`: one function for each rule of the spec that returns its problems, one check that applies it to the committed render and one that applies it to a fixture that breaks it; add the kind `Seaweed` to the data safety check of `tests/gate/k8s_checks/argocd_apps.py`. The checks fail on the base tree, which has no store
  - Verification: `$ uv run devops ci --check --only k8s` fails and names the object store
- [ ] 1.2 Add namespace `object-store`, the Applications `seaweedfs-operator` and `object-store`, the AppProject entries, `k8s/object-store/kustomization.yaml`, `seaweed.yaml`, `networkpolicy.yaml`, `poddisruptionbudgets.yaml` and `operator-values.yaml`
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. The Secrets of the store have ClusterSecret rows

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/invariants/test_k8s_manifests.py`. Changes: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/invariants/test_k8s_manifests.py`, `k8s/README.md`.

- [ ] 2.1 Add the rows `object-store/seaweedfs-admin` and `object-store/seaweedfs-s3` to the expected table of `test_table_holds_each_secret_entry_with_its_source_and_restarts`, a test of the two rows, and the key `seaweedfs_admin_password` to the keyring-only keys of `test_keyring_sources_are_managed_keys_or_declared_keyring_only`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/invariants/test_k8s_manifests.py` fails
- [ ] 2.2 Add the two rows and `SEAWEEDFS_ADMIN_AUTH_KEY` to `src/devops_cli/k8s/cluster_secrets.py`, and their rows to the Cluster Secrets table of `k8s/README.md`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/invariants/test_k8s_manifests.py` passes

## 3. deploy-stack installs the store with stack infra

Kind: behavior. Reads: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/commands/k8s/test_k8s.py`. Changes: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `tests/commands/k8s/test_k8s.py`.

- [ ] 3.1 Write `test_deploy_stack_installs_the_object_store_operator_after_cert_manager_and_the_store_after_the_charts` in `tests/commands/k8s/test_k8s.py`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` fails
- [ ] 3.2 Add the repository, the release and the post-Helm path `object-store` to stack `infra`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py` passes

## 4. The store alerts and has a dashboard

Kind: manifest. Reads: `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/kustomization.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/seaweedfs.json` (new), `k8s/monitoring/dashboards/kustomization.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [ ] 4.1 Add the `seaweedfs` group of five alerts, the four SeaweedFS series to `SERVED_SERIES`, the dashboard of tag 4.54 with the lint changes, and its ConfigMap `grafana-storage-dashboards`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py tests/prometheus/test_k8s_monitoring_dashboards.py` passes, `$ uv run devops grafana dashboards lint k8s/monitoring/dashboards/seaweedfs.json` finds no problem, and `$ uv run devops ci --check --only k8s` passes

## 5. The build test

Kind: other. Changes: `k8s/object-store/build-test/` (new).

- [ ] 5.1 Add the kustomization of namespace `object-store-build-test` with the label `backup-client: "true"`, the boto3 Job and the minio-go Job, each with a restricted security context and a digest-pinned image
  - Verification: `$ kubectl kustomize k8s/object-store/build-test` renders the namespace, the ConfigMap and the two Jobs

## 6. Documents

Kind: other. Changes: `k8s/README.md`, `k8s/catalog.toml`, `docs/adr/0034-the-object-store-is-seaweedfs-with-its-operator.md` (new), `docs/adr/README.md`.

- [ ] 6.1 Add ADR 0034 and its index row, the catalog entry `object-store`, and the README section `Object Store` (version rule, rollout, build test, node restore), the alert rows and the dashboard row
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- The general settings of the operator move to dan-petty/infra in a later item; this change keeps them in `k8s/object-store/operator-values.yaml`.
- Pending a person: run `uv run devops k8s push-secrets --only object-store/seaweedfs-admin --only object-store/seaweedfs-s3` after the merge, then the same command with `--plan` until each key shows `unchanged`.
- Pending a person: run the build test of the README section `Build test` and post its results on the pull request.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
