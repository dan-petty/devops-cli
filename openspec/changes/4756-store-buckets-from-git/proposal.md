# Proposal: #4756

## Why
Closes #4756. The object store of #4750 runs, but its buckets, quotas, anonymous read, lifecycle rules and keys are not in git. A person makes them in the admin UI, so they drift and nothing restores them. The SeaweedFS operator that runs the store has a custom resource for each of them, so git can hold them with no reconcile code.

## What Changes
- `k8s/object-store/buckets.yaml` (new): the four platform buckets `reports` (20Gi), `reports-private` (20Gi), `cache` (10Gi) and `argo-artifacts` (10Gi), each a `Bucket` with an enforced quota and `reclaimPolicy: Retain`, and one `BucketLifecyclePolicy` for each. Only `reports` and `reports-private` have `anonymousRead`. Each bucket aborts an incomplete multipart upload after 1 day; prefix `studies/` of `reports-private` expires after 90 days; `cache` and `argo-artifacts` expire after 7 days.
- `k8s/object-store/writers.yaml` (new): for each writer, the same five objects: `S3Identity`, `S3Policy`, `S3PolicyBinding` and `S3Credentials` in namespace `object-store`, and a `ResourceReferenceGrant` in the namespace of the writer. Writer `devops` works on `reports`, `reports-private` and `cache`; writer `argo` works on `argo-artifacts`. The `S3Credentials` of each writer reads its key pair from Secret `object-store-<writer>` in the writer namespace.
- `src/devops_cli/k8s/cluster_secrets.py`: the rows `devops/object-store-devops` and `argo-workflows/object-store-argo`, each with `accessKey` and `secretKey` from keyring-only keys that the push generates. The keyring stays the source of each key pair.
- `k8s/object-store/operator-values.yaml`: `watchNamespaces` adds `devops` and `argo-workflows`, so the operator reads the Secret and the grant of each writer.
- `k8s/object-store/kustomization.yaml`: no `namespace` transformer, because the grants live in the writer namespaces. Each object names its own namespace; the `Seaweed` CR gets `namespace: object-store`.
- `k8s/argocd/apps/projects.yaml`: the project `homelab` ignores the two pushed Secrets as orphans.
- The `k8s` row: a new module `tests/gate/k8s_checks/object_store_buckets.py` holds the rules of the buckets, the lifecycle rules, the anonymous read, the writer keys, the grants, the watch scope and the kinds of the render. The Secret rule of `tests/gate/k8s_checks/object_store.py` reads the namespace of a `secretRef`, and the fixed `watchNamespaces` value leaves the values rule.
- `k8s/README.md`: the buckets and keys of the store, the scope and namespace of each CR, the new Secret rows, and the rollout step of the push.
- The change alters manifests, the `CLUSTER_SECRETS` table and the access of the store, so it carries a spec delta.
- The change fits one pull request.

## Capabilities
- `object-store`: ADDED requirements for the buckets, the anonymous read, the lifecycle rules, the writer policies, the writer keys and grants, the watch scope, the kinds of the render and the Secret rows of the writer keys. MODIFIED requirement "Every Secret that the store reads has a ClusterSecret row".

## Impact
- After Argo CD syncs `main`, the operator watches three namespaces and makes the four buckets with their quotas, the anonymous read of the two report buckets, the lifecycle rules, the two identities and their policies. A quota or a rule that a person changes goes back to the git value at the next reconcile of the operator.
- The `S3Credentials` of each writer stays `Pending` (`SecretNotFound`) and retries until a person pushes its Secret with `devops k8s push-secrets`. No pod reads the two Secrets yet, so no pod waits on them.
- The operator gets the Role of its chart in `devops` and `argo-workflows`.
- No NetworkPolicy changes: the operator reaches the API server and the filer and master gRPC ports through the policies of #4750, and this change adds no S3 client.

## Feasibility
- Operator: the live cluster runs `chrislusf/seaweedfs-operator:1.0.45` (chart 0.1.48), not 1.0.43, with `--watch-namespaces=object-store` (`kubectl -n object-store get deploy seaweedfs-operator`, read-only). `kubectl get crd` lists the Namespaced CRDs `buckets`, `bucketlifecyclepolicies`, `s3identities`, `s3credentials`, `s3policies`, `s3policybindings` and `resourcereferencegrants` of group `seaweed.seaweedfs.com`, version `v1`, and no CR of these kinds exists.
- Fields: the live `Bucket` CRD has `spec.quota.size` and `enforce` (default true), `reclaimPolicy` `Retain` or `Delete`, `anonymousRead`, `access`, and exactly one of `seaweedRef` or `clusterRef` (`clusterRef` is the deprecated alias, `api/v1/bucket_types.go`). `BucketLifecyclePolicy` has `bucketRef` and rules with `prefix`, `expiration.days` (minimum 1), `abortIncompleteMultipartUpload.daysAfterInitiation` and `status`; it has no expiration date. `S3Credentials` has `identityRef` and `secretRef` with `namespace`, `accessKeyField` and `secretKeyField`.
- Namespaces: at tag `seaweedfs-operator-0.1.48`, `S3Credentials.identityRef`, `S3PolicyBinding.policyRef` and its subjects, and `BucketLifecyclePolicy.bucketRef` resolve in the namespace of their own CR. A cross-namespace `secretRef` needs a `ResourceReferenceGrant` in the namespace of the Secret, and that Secret "must already exist and supplies the key pair; the controller never creates Secrets in foreign namespaces" (`api/v1/s3credentials_types.go`, `internal/controller/s3credentials_controller.go`). A `Pending` credential requeues.
- Watch scope: `cmd/main.go` sets `Cache.DefaultNamespaces` from `--watch-namespaces`, and the grant check lists the grants of the Secret namespace and gets the Secret through that cache (`internal/controller/referencegrant.go`). So the operator must watch each writer namespace. The chart renders the manager Role and its binding in each namespace of `watchNamespaces` (`deploy/helm/templates/rbac/role.yaml`).
- Policies: SeaweedFS 4.54 authorizes an identity with attached policies by those policies alone when the IAM integration is off (`authorizationRoute` and `evaluateAttachedIAMPolicies` in `weed/s3api/auth_credentials.go`), so `iam: false` of #4750 keeps the policies of the `S3PolicyBinding` in force. An identity with no matching statement gets `AccessDenied`.
- The operator writes identities and policies through the filer IAM gRPC API with the JWT key of Secret `seaweedfs-security-config`, and buckets, quotas and anonymous read through the embedded `weed shell` (`internal/controller/iam_admin.go`, `bucket_admin.go`). Both use the filer and master gRPC ports that `object-store-perimeter` already admits between the pods of the namespace.
- External Secrets Operator is not on the cluster (`kubectl get crd` lists no `external-secrets.io` CRD on 2026-11-22), so the platform keys cannot come from an ESO `Password` generator here.

## Existing Tool Considered
- The SeaweedFS operator CRs (Apache-2.0, maintained) cover the whole need, as the alternatives check of 2026-11-14 records. The change writes no reconcile script, PostSync Job, CronJob or image.
- The fallback of the issue (the upstream chart and a `weed shell` Job) is not needed: every field of the design exists in the CRDs of operator 1.0.45.
- Build cost: about 400 lines of YAML and check code, about 150k tokens and 3 hours, because the operator does the reconcile.
- The change deletes the fixed `watchNamespaces` value of the values rule in `tests/gate/k8s_checks/object_store.py`; the new watch rule replaces it.
