# Tasks

## 1. The writer keys have ClusterSecret rows

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/invariants/test_k8s_manifests.py`. Changes: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/invariants/test_k8s_manifests.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_qdrant_security.py`, `k8s/README.md`.

- [x] 1.1 Add the rows `devops/object-store-devops` and `argo-workflows/object-store-argo` to the expected table of `test_table_holds_each_secret_entry_with_its_source_and_restarts`, write `test_each_writer_key_of_the_store_is_generated_in_the_keyring`, add the four keys `object_store_<writer>_access_key` and `object_store_<writer>_secret_key` to the keyring-only keys of `test_keyring_sources_are_managed_keys_or_declared_keyring_only`, and add the two Secrets to the expected pushes of the `infra` and `devops` stacks
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/invariants/test_k8s_manifests.py` fails
- [x] 1.2 Add the two rows to `CLUSTER_SECRETS`, and their table rows and note to the Cluster Secrets section of `k8s/README.md`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/invariants/test_k8s_manifests.py` passes

## 2. The k8s row checks the buckets, the keys and the watch scope

Kind: manifest. Reads: `tests/gate/k8s_checks/object_store.py`, `tests/gate/k8s_render.py`, `src/devops_cli/k8s/cluster_secrets.py`. Changes: `tests/gate/k8s_checks/object_store_buckets.py` (new), `tests/gate/k8s_checks/object_store.py`, `k8s/object-store/buckets.yaml` (new), `k8s/object-store/writers.yaml` (new), `k8s/object-store/kustomization.yaml`, `k8s/object-store/seaweed.yaml`, `k8s/object-store/operator-values.yaml`, `k8s/argocd/apps/projects.yaml`.

- [ ] 2.1 Write `tests/gate/k8s_checks/object_store_buckets.py`: one function for each rule of the spec that returns its problems, one check that applies it to the committed render, and one that applies it to a fixture that breaks it. Make the Secret rule of `object_store.py` read the namespace of a `secretRef`, with a fixture check, and move `watchNamespaces` from its values rule to the new watch rule. The checks fail on the base tree, which has no bucket
  - Verification: `$ uv run devops ci --check --only k8s` fails and names `object_store_buckets`
- [ ] 2.2 Add `buckets.yaml` and `writers.yaml`, list them in the kustomization and drop its `namespace` transformer, give the `Seaweed` CR `namespace: object-store`, add `devops` and `argo-workflows` to `watchNamespaces`, and add the two Secrets to the orphan ignores of the project `homelab`
  - Verification: `$ uv run devops ci --check --only k8s` passes, and `$ uv run devops k8s lint` finds no problem

## 3. Documents

Kind: other. Changes: `k8s/README.md`.

- [ ] 3.1 Add the section `Buckets and keys` to the Object Store section of `k8s/README.md` (the buckets, the writers, the scope and namespace of each CR), and update the Application row, the security bullet of the S3 identities, the clients, the rollout, the operator scope and the folder tree
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- The tenant backup buckets `backups-*`, their identities, policies and keys come from the tenant chart of `dan-petty/infra#14`.
- The read-only identity `cloud-backup` and its key come with #4770.
- The 90-day rule of the version-review HTML comes when #4733 names its bucket and prefix.
- Pending a person: run `uv run devops k8s push-secrets --only devops/object-store-devops --only argo-workflows/object-store-argo --plan`, then the same command without `--plan`, then `--plan` again until each key shows `unchanged`.
- Pending a person: run the live checks of the spec after the sync: the buckets and quotas, the anonymous requests, the key of `argo` on `reports`, the credentials, the watch scope, the lifecycle rules and the expiry on a branch revision.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
