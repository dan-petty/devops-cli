# Design

## Decisions

- **Scope of the item.** This change makes the four platform buckets of the devops-cli workloads, with their quotas, their anonymous read and their lifecycle rules. The tenant backup buckets (`backups-*`), the writer identities and keys, and the read-only identity `cloud-backup` come from the tenant chart of `dan-petty/infra#14`, which is a separate issue: one generic CR form for each tenant namespace, with a key pair from an ESO `Password` generator. The 90-day rule for the version-review HTML waits for #4733 to name its bucket and prefix: a rule on a guessed prefix expires nothing, or other objects.
- **Scope and namespace of each CR.** Every CRD of the operator is Namespaced. Each bucket and its lifecycle policy live in the namespace of the workload that writes the bucket, so the tenant chart can put the same form in each tenant namespace and a later writer key stays in its own namespace:

  | Kind | Count | Namespace | Why |
  | :--- | :--- | :--- | :--- |
  | `Bucket` `reports`, `reports-private`, `cache` | 3 | `devops` | The namespace of the devops-cli workloads that write them |
  | `Bucket` `argo-artifacts` | 1 | `argo-workflows` | The namespace of the Argo Workflows controller and its runs |
  | `BucketLifecyclePolicy` | 4 | The namespace of its bucket | Its `bucketRef` names a `Bucket` of its own namespace, and it takes the cluster from that bucket |
  | `ResourceReferenceGrant` `object-store-buckets` | 1 | `object-store` | The operator checks a `clusterRef` to another namespace against the grants of the namespace of the `Seaweed` CR |

- **Buckets.** Each `Bucket` sets `clusterRef` (`seaweedfs` in `object-store`), `quota.size` with `enforce: true`, and `reclaimPolicy: Retain`. `local-path` does not enforce the size of a claim, so the quotas are the limits. `seaweedRef` is the same reference under the name that the other CRDs use; the CRD requires exactly one of the two (`api/v1/bucket_types.go`), and the item names `clusterRef`.
- **Grant.** One grant in `object-store` admits the kind `Bucket` of group `seaweed.seaweedfs.com` from namespace `devops` and from namespace `argo-workflows`, each by name, to the `Seaweed` CR `seaweedfs` by name. The Bucket controller refuses a `clusterRef` to another namespace with no such grant, and sets `ClusterRefForbidden` (`internal/controller/bucket_controller.go`, `referencegrant.go`). A `BucketLifecyclePolicy` needs no grant: it reads the `Seaweed` CR of its bucket (`internal/controller/bucketlifecyclepolicy_controller.go`).
- **Anonymous read.** `anonymousRead: true` only on `reports` and `reports-private`. The operator grants the reserved identity `anonymous` the action `Read` on the bucket, which allows GET and not List. No `access` entry names `anonymous`.
- **Lifecycle.** One `BucketLifecyclePolicy` for each bucket, named as the bucket. Each has the rule `abort-incomplete-multipart` (`abortIncompleteMultipartUpload.daysAfterInitiation: 1`, no prefix). `reports-private` adds `studies` (prefix `studies/`, 90 days); `cache` and `argo-artifacts` add `expire` (7 days). No bucket named `backups-*` may have an expiration rule. The CRD has no expiration date: `expiration.days` has a minimum of 1.
- **Keys.** This change adds no `S3Identity`, `S3Policy`, `S3PolicyBinding` or `S3Credentials`, and no row to `CLUSTER_SECRETS`. The S3 gateway keeps its identities file with no identity, so it refuses each signed request until the tenant chart adds an identity; only the anonymous GET of the report buckets works.
- **Watch scope.** `watchNamespaces: [object-store, devops, argo-workflows]`: the store and the namespace of each bucket. The operator reads its CRs only through the cache of the watched namespaces (`cmd/main.go`, `Cache.DefaultNamespaces`), so a bucket in a namespace that it does not watch never reconciles. The chart then renders its manager Role and binding in each of the three namespaces, in place of a ClusterRole over every namespace.
- **Kustomization.** `k8s/object-store/kustomization.yaml` has no `namespace` transformer, because the transformer would move the buckets into `object-store`. Each object names its namespace. The root kustomization makes the namespaces `devops` and `argo-workflows` before deploy-stack applies the folder.
- **Argo CD.** Application `object-store` of #4750 applies the new files at sync-wave `0` after the operator, with automated sync, `prune`, `selfHeal`, 5 retries and `SkipDryRunOnMissingResource=true`. The project `homelab` already lists `devops` and `argo-workflows` as destinations. A changed CR goes back to git at the next sync, and the operator restores a changed quota or rule at its next reconcile.
- **Network.** No NetworkPolicy changes. The operator reaches the API server through `object-store-operator-egress`, and the filer gRPC port 18888 and the master gRPC port 19333 through `object-store-perimeter-egress` and `object-store-perimeter-ingress`. This change adds no S3 client, so no namespace gets the label `backup-client: "true"`.
- **Checks.** `tests/gate/k8s_checks/object_store_buckets.py` reads the shared render of `k8s/object-store`. Each rule is a function that returns its problems; one check applies it to the committed render, and one applies it to a fixture that breaks the rule and asserts that the problem names the object, as `object_store.py` does. A unit test of `tests/k8s/test_cluster_secret_plan.py` holds the table to no row of a store key.

## Rejected alternatives

- **All store CRs in namespace `object-store`.** A writer key then reaches across namespaces, and the grant of each tenant namespace in the tenant chart cannot scope it.
- **ClusterSecret rows for the writer keys, pushed by `devops k8s push-secrets`.** The owner refused it: the key pair would live in the workstation keyring. The tenant chart makes each pair with an ESO `Password` generator.
- **Hand-written writer CRs in `k8s/object-store/`.** The per-tenant form belongs in the tenant chart that the tenant namespaces read, and a copy here would drift from it.
- **A grant with a `namespaceSelector`.** The operator then reads the labels of each source namespace, and a new namespace with a matching label gets access to the store. Two names keep the grant narrow.
- **An empty `watchNamespaces`.** The chart then renders the manager rules as a ClusterRole over every namespace (`deploy/helm/templates/rbac/role.yaml`, else branch), with write access to the Secrets and the workloads of each namespace.
- **The present watch scope of `object-store` only.** The operator would never see the buckets of `devops` and `argo-workflows`.
- **Cluster-scoped CRs.** The `Bucket` CRD is Namespaced, so the API server refuses a cluster-scoped object.
- **`Bucket.spec.access` for a writer.** No writer identity exists in this change, and the tenant chart grants access with `S3Policy` and `S3PolicyBinding`.
