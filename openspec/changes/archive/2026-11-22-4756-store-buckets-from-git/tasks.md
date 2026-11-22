# Tasks

## 1. No key rows in the ClusterSecret table

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_secrets.py`, `tests/k8s/test_cluster_secret_plan.py`. Changes: `tests/k8s/test_cluster_secret_plan.py`.

- [x] 1.1 Write `test_no_row_holds_a_key_of_the_object_store`: no row of `CLUSTER_SECRETS` has a name that starts with `object-store-`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py` passes

## 2. The k8s row checks the buckets and the watch scope

Kind: manifest. Reads: `tests/gate/k8s_checks/object_store.py`, `tests/gate/k8s_render.py`. Changes: `tests/gate/k8s_checks/object_store_buckets.py` (new), `tests/gate/k8s_checks/object_store.py`, `k8s/object-store/buckets.yaml` (new), `k8s/object-store/kustomization.yaml`, `k8s/object-store/seaweed.yaml`, `k8s/object-store/operator-values.yaml`, `src/devops_cli/k8s/cluster_secrets.py`.

- [x] 2.1 Write `tests/gate/k8s_checks/object_store_buckets.py`: one function for each rule of the spec that returns its problems, one check that applies it to the committed render, and one that applies it to a fixture that breaks it. Move `watchNamespaces` from the values rule of `object_store.py` to the new watch rule, which holds it to `[object-store]`. The kind rule refuses a `ResourceReferenceGrant` and an object outside `object-store`. The checks fail on the base tree, which has no bucket, and on a tree with the buckets in `devops` and `argo-workflows`
  - Verification: `$ uv run devops ci --check --only k8s` fails and names `object_store_buckets`
- [x] 2.2 Add `buckets.yaml` with the buckets and lifecycle policies and no grant, and list it in the kustomization, whose `namespace` transformer puts them in `object-store`. Keep `watchNamespaces: [object-store]` and name the reason in its comment. Make the comments on the S3 identities file in `seaweed.yaml` and `cluster_secrets.py` name identity `anonymous` of the filer
  - Verification: `$ uv run devops ci --check --only k8s` passes, and `$ kubectl apply --dry-run=server` accepts the Buckets and the policies of the render
- [x] 2.3 Render the pinned chart with the values of the branch and read its RBAC
  - Verification: `$ helm template seaweedfs-operator seaweedfs-operator --repo https://seaweedfs.github.io/seaweedfs-operator --version 0.1.48 --namespace object-store -f k8s/object-store/operator-values.yaml` renders each Role and RoleBinding in `object-store`, and its one ClusterRoleBinding binds a ClusterRole that only reads namespaces and storage classes

## 3. Documents

Kind: other. Changes: `k8s/README.md`.

- [x] 3.1 Add the section `Buckets` to the Object Store section of `k8s/README.md` (the buckets, the scope and namespace of each CR, the watch scope), and update the Application row, the S3 identities, the rollout check and the folder tree
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- The tenant backup buckets `backups-*`, the writer identities, policies and keys, and the read-only identity `cloud-backup` come from the tenant chart of `dan-petty/infra#14`, with ESO keys.
- The 90-day rule of the version-review HTML comes when #4733 names its bucket and prefix.
- Pending a person: run the live checks of the spec after the sync: the buckets and quotas, the anonymous requests, the watch scope and the Roles of the operator, the lifecycle rules and the expiry on a branch revision.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
