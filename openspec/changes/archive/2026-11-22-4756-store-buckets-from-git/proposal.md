# Proposal: #4756

## Why
Closes #4756. The object store of #4750 runs, but its buckets, quotas, anonymous read and lifecycle rules are not in git. A person makes them in the admin UI, so they drift and nothing restores them. The SeaweedFS operator that runs the store has a custom resource for each of them, so git can hold them with no reconcile code.

## What Changes
- `k8s/object-store/buckets.yaml` (new): the four platform buckets `reports` (20Gi), `reports-private` (20Gi) and `cache` (10Gi) in namespace `devops`, and `argo-artifacts` (10Gi) in namespace `argo-workflows`. Each is a `Bucket` with a `clusterRef` to the store, an enforced quota and `reclaimPolicy: Retain`, and has one `BucketLifecyclePolicy` in its namespace. Only `reports` and `reports-private` have `anonymousRead`. Each bucket aborts an incomplete multipart upload after 1 day; prefix `studies/` of `reports-private` expires after 90 days; `cache` and `argo-artifacts` expire after 7 days. One `ResourceReferenceGrant` in `object-store` admits the buckets of the two namespaces to the store.
- `k8s/object-store/operator-values.yaml`: `watchNamespaces` adds `devops` and `argo-workflows`, so the operator reconciles the buckets and their rules there.
- `k8s/object-store/kustomization.yaml`: no `namespace` transformer, because the buckets live in their own namespaces. Each object names its own namespace; the `Seaweed` CR gets `namespace: object-store`.
- The `k8s` row: a new module `tests/gate/k8s_checks/object_store_buckets.py` holds the rules of the buckets, the grant, the anonymous read, the lifecycle rules, the watch scope and the kinds of the render. The fixed `watchNamespaces` value leaves the values rule of `tests/gate/k8s_checks/object_store.py`.
- `tests/k8s/test_cluster_secret_plan.py`: a unit test that `CLUSTER_SECRETS` holds no row of a store key.
- `k8s/README.md`: the buckets of the store, and the scope and namespace of each CR.
- The writer identities and keys, the tenant buckets `backups-*` and the identity `cloud-backup` are not in this change: they come from the tenant chart of `dan-petty/infra#14`.
- The change alters manifests and the access of the store, so it carries a spec delta.
- The change fits one pull request.

## Capabilities
- `object-store`: ADDED requirements for the buckets, the grant, the anonymous read, the lifecycle rules, the watch scope, the kinds of the render and the absence of key rows in `CLUSTER_SECRETS`.

## Impact
- After Argo CD syncs `main`, the operator watches three namespaces and makes the four buckets with their quotas, the anonymous read of the two report buckets and the lifecycle rules. A quota or a rule that a person changes goes back to the git value at the next reconcile of the operator.
- No key can write a bucket yet: the S3 gateway refuses each signed request until the tenant chart adds an identity. The anonymous GET of an object of `reports` and `reports-private` works.
- The operator gets the Role of its chart in `devops` and `argo-workflows`.
- No Secret, row of `CLUSTER_SECRETS` or person step of `devops k8s push-secrets` comes with the change.
- No NetworkPolicy changes: the operator reaches the API server and the filer and master gRPC ports through the policies of #4750, and this change adds no S3 client.

## Feasibility
- Operator: the live cluster runs `chrislusf/seaweedfs-operator:1.0.45` (chart 0.1.48), not 1.0.43, with `--watch-namespaces=object-store` (`kubectl -n object-store get deploy seaweedfs-operator`, read-only). `kubectl get crd` lists the Namespaced CRDs `buckets`, `bucketlifecyclepolicies` and `resourcereferencegrants` of group `seaweed.seaweedfs.com`, version `v1`, and no CR of these kinds exists.
- Fields: the `Bucket` CRD has `spec.quota.size` and `enforce` (default true), `reclaimPolicy` `Retain` or `Delete`, `anonymousRead`, `access`, and exactly one of `clusterRef` or `seaweedRef` (`api/v1/bucket_types.go` at tag `seaweedfs-operator-0.1.48`). `BucketLifecyclePolicy` has `bucketRef` and rules with `prefix`, `expiration.days` (minimum 1), `abortIncompleteMultipartUpload.daysAfterInitiation` and `status`; it has no expiration date.
- Namespaces: at tag `seaweedfs-operator-0.1.48`, the Bucket controller resolves a `clusterRef` to another namespace only when a `ResourceReferenceGrant` in the namespace of the `Seaweed` CR admits kind `Bucket` from the namespace of the bucket, and else keeps the bucket `Pending` with `ClusterRefForbidden` (`internal/controller/bucket_controller.go`, `internal/controller/referencegrant.go`). `BucketLifecyclePolicy.bucketRef` names a `Bucket` of its own namespace, and the policy reads the `Seaweed` CR of that bucket with no grant check (`internal/controller/bucketlifecyclepolicy_controller.go`).
- Watch scope: `cmd/main.go` sets `Cache.DefaultNamespaces` from `--watch-namespaces`, so the operator sees only the CRs of the watched namespaces. The chart renders the manager Role and its binding in each namespace of `watchNamespaces` (`deploy/helm/templates/rbac/role.yaml`).
- The operator writes buckets, quotas, anonymous read and lifecycle rules through the embedded `weed shell` and the filer (`internal/controller/bucket_admin.go`), over the filer and master gRPC ports that `object-store-perimeter-ingress` and `object-store-perimeter-egress` already admit between the pods of the namespace.
- The root kustomization makes namespaces `devops` and `argo-workflows` (`k8s/namespaces.yaml`) before deploy-stack applies `k8s/object-store` after the charts.

## Existing Tool Considered
- The SeaweedFS operator CRs (Apache-2.0, maintained) cover the whole need, as the alternatives check of 2026-11-14 records. The change writes no reconcile script, PostSync Job, CronJob or image.
- The fallback of the issue (the upstream chart and a `weed shell` Job) is not needed: every field of the design exists in the CRDs of operator 1.0.45.
- Build cost: about 300 lines of YAML and check code, about 100k tokens and 2 hours, because the operator does the reconcile.
- The change deletes the fixed `watchNamespaces` value of the values rule in `tests/gate/k8s_checks/object_store.py`; the new watch rule replaces it.
