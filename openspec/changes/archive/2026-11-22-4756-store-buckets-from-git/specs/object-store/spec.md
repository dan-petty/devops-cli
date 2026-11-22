## ADDED Requirements

### Requirement: The store declares the platform buckets with their quotas
The render of `k8s/object-store` SHALL hold a `Bucket` for `reports` (20Gi), `reports-private` (20Gi), `cache` (10Gi) and `argo-artifacts` (10Gi). Each `Bucket` SHALL be in namespace `object-store`, SHALL name the `Seaweed` CR `seaweedfs` of its own namespace in `clusterRef`, and SHALL set `quota.size`, a quota that is not `enforce: false`, and `reclaimPolicy: Retain`.

#### Scenario: The committed buckets
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with the four buckets in `object-store`, their quotas, `reclaimPolicy: Retain` and `seaweedfs` in `clusterRef`

#### Scenario: A bucket that deletes its data
- **WHEN** `uv run devops ci --check --only k8s` runs the bucket rule on the committed buckets with `reclaimPolicy: Delete` on `cache`
- **THEN** the rule reports a problem that names `Bucket/cache`

#### Scenario: A bucket in the namespace of its writer
- **WHEN** `uv run devops ci --check --only k8s` runs the bucket rule on the committed buckets with `cache` in namespace `devops` and a `clusterRef` to `object-store/seaweedfs`
- **THEN** the rule reports a problem that names the namespace of `Bucket/cache` and a problem that names its `clusterRef`

#### Scenario: The buckets on the cluster
- **WHEN** a person runs `kubectl get buckets.seaweed.seaweedfs.com -A -o yaml` after the sync
- **THEN** the output has `reports` 20Gi, `reports-private` 20Gi, `cache` 10Gi and `argo-artifacts` 10Gi, all in namespace `object-store`, each `Ready` with `reclaimPolicy: Retain` and a `clusterRef` to `seaweedfs`, and a quota that a person changes with `weed shell` `s3.bucket.quota` goes back to the git value at the next reconcile

### Requirement: One CR makes each bucket
No two `Bucket` CRs of the render SHALL have the same bucket name: `spec.name`, else the name of the CR. The bucket rule SHALL check each CR, so a second CR of a bucket cannot hide behind the first.

#### Scenario: Two CRs of one bucket
- **WHEN** `uv run devops ci --check --only k8s` runs the bucket rule on the committed buckets with a second CR `cache-copy` whose `spec.name` is `cache`
- **THEN** the rule reports a problem that names `Bucket/cache` and both CRs

#### Scenario: A second CR that deletes the data of a bucket
- **WHEN** `uv run devops ci --check --only k8s` runs the bucket rule on the committed buckets with a second CR `cache-copy` of `cache`, before the committed CR, with `reclaimPolicy: Delete`
- **THEN** the rule reports a problem that names `Bucket/cache-copy`

### Requirement: Only the report buckets have anonymous read
Only the buckets `reports` and `reports-private` SHALL set `anonymousRead: true`, and no `Bucket` SHALL name the user `anonymous` in `access`. No bucket named `backups-*` SHALL have anonymous access.

#### Scenario: The committed anonymous read
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with `anonymousRead: true` on `reports` and `reports-private` only

#### Scenario: A backup bucket with anonymous read
- **WHEN** `uv run devops ci --check --only k8s` runs the anonymous rule on a fixture bucket `backups-example` with `anonymousRead: true`
- **THEN** the rule reports a problem that names `Bucket/backups-example`

#### Scenario: Anonymous requests on the cluster
- **WHEN** a person puts a test object in `reports`, `reports-private` and `cache` through the filer path `/buckets/<bucket>/` of a filer pod, and sends an anonymous GET of each object and an anonymous List of each bucket to the S3 gateway
- **THEN** `reports` and `reports-private` return 200 for the GET and `AccessDenied` for the List, and `cache` returns `AccessDenied` for the GET

### Requirement: Each bucket has its lifecycle rules in git
Each `Bucket` of the render SHALL have exactly one `BucketLifecyclePolicy` in its namespace, with an enabled rule with no prefix that aborts an incomplete multipart upload after 1 day. Prefix `studies/` of `reports-private` SHALL expire after 90 days, and `cache` and `argo-artifacts` SHALL expire after 7 days. No bucket named `backups-*` SHALL have an expiration rule.

#### Scenario: The committed lifecycle rules
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with one policy for each bucket and the rules of this requirement

#### Scenario: A backup bucket with an expiration rule
- **WHEN** `uv run devops ci --check --only k8s` runs the lifecycle rule on a fixture bucket `backups-example` whose policy has an expiration rule
- **THEN** the rule reports a problem that names `Bucket/backups-example`

#### Scenario: A bucket with no lifecycle policy
- **WHEN** `uv run devops ci --check --only k8s` runs the lifecycle rule on the committed render with no policy for `reports`
- **THEN** the rule reports a problem that names `Bucket/reports`

#### Scenario: Expiry on the cluster
- **WHEN** a person runs `kubectl get bucketlifecyclepolicies.seaweed.seaweedfs.com -A -o yaml` after the sync, and on a branch revision with a 1-day expiration rule on prefix `lifecycle-test/` of `cache` puts a test object there and starts a multipart upload
- **THEN** the output holds the rules of git, and after the S3 lifecycle pass of the next day the test object and the incomplete upload are gone

### Requirement: The operator watches only the store namespace
`watchNamespaces` of `k8s/object-store/operator-values.yaml` SHALL be exactly `[object-store]`, and each `Bucket` and `BucketLifecyclePolicy` of the render SHALL be in that namespace. The chart gives each watched namespace the manager Role of the operator, which can read and write every Secret of the namespace, so the operator SHALL have no Role or RoleBinding in `devops`, `argo-workflows` or another namespace of a writer, and no ClusterRole over the resources of every namespace.

#### Scenario: The committed watch scope
- **WHEN** `uv run devops ci --check --only k8s` reads the values and renders `k8s/object-store`
- **THEN** the row passes with `object-store` only

#### Scenario: A watched writer namespace
- **WHEN** `uv run devops ci --check --only k8s` runs the watch rule on values with `watchNamespaces: [object-store, devops, argo-workflows]`
- **THEN** the rule reports a problem that names `watchNamespaces`

#### Scenario: A watch of every namespace
- **WHEN** `uv run devops ci --check --only k8s` runs the watch rule on values with `watchNamespaces: []`
- **THEN** the rule reports a problem that names `watchNamespaces`

#### Scenario: The chart render
- **WHEN** a person runs `helm template seaweedfs-operator seaweedfs-operator --repo https://seaweedfs.github.io/seaweedfs-operator --version <version> --namespace object-store -f k8s/object-store/operator-values.yaml`, with the `targetRevision` of `k8s/argocd/apps/seaweedfs-operator.yaml` as the version
- **THEN** each Role and RoleBinding of the output is in namespace `object-store`, the one ClusterRoleBinding binds ClusterRole `seaweedfs-operator-manager-role`, which only reads namespaces and storage classes, and the operator arguments hold `--watch-namespaces=object-store`

#### Scenario: The live operator
- **WHEN** a person runs `kubectl -n object-store get deploy seaweedfs-operator -o jsonpath='{.spec.template.spec.containers[0].args}'` and `kubectl get roles,rolebindings -A` after the sync
- **THEN** the arguments hold `--watch-namespaces=object-store`, and each Role and RoleBinding whose name starts with `seaweedfs-operator-` is in namespace `object-store`

### Requirement: The store render holds no reconcile workload
The render of `k8s/object-store` SHALL hold only the kinds `Seaweed`, `Bucket`, `BucketLifecyclePolicy`, `NetworkPolicy` and `PodDisruptionBudget`, each in namespace `object-store`: no Job, CronJob, Pod, workload or script, and no `ResourceReferenceGrant`, because no CR of another namespace names the store.

#### Scenario: The committed render
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with only the kinds of this requirement, all in `object-store`

#### Scenario: A reconcile Job
- **WHEN** `uv run devops ci --check --only k8s` runs the kind rule on the committed render with a fixture `Job` `bucket-reconcile`
- **THEN** the rule reports a problem that names `Job/bucket-reconcile`

#### Scenario: A reference grant
- **WHEN** `uv run devops ci --check --only k8s` runs the kind rule on the committed render with a fixture `ResourceReferenceGrant` `object-store-buckets`
- **THEN** the rule reports a problem that names `ResourceReferenceGrant/object-store-buckets`

#### Scenario: A policy in the namespace of its writer
- **WHEN** `uv run devops ci --check --only k8s` runs the kind rule on the committed render with the policy `argo-artifacts` in namespace `argo-workflows`
- **THEN** the rule reports a problem that names `BucketLifecyclePolicy/argo-artifacts`

#### Scenario: The live namespace
- **WHEN** a person runs `kubectl get jobs,cronjobs -n object-store` and `kubectl get pods -n object-store -o jsonpath='{.items[*].spec.containers[*].image}'` after the sync
- **THEN** the first command reports no resources, and the second lists only the SeaweedFS images of the store and the operator

### Requirement: No key rows in the ClusterSecret table
`CLUSTER_SECRETS` SHALL hold no row for a key of the store: no row whose name starts with `object-store-`. The key pair of a writer comes from an ESO `Password` generator of the tenant chart, not from the keyring.

#### Scenario: The table rows
- **WHEN** a unit test reads `CLUSTER_SECRETS` in `src/devops_cli/k8s/cluster_secrets.py`
- **THEN** no row has a name that starts with `object-store-`

## MODIFIED Requirements

### Requirement: The S3 gateway refuses a request with no identity
Secret `object-store/seaweedfs-s3` SHALL hold key `s3.json` with an identities file that has no identity, and the S3 gateway SHALL read it, so it refuses a request with no valid signature unless an identity of the filer allows the request. The operator gives identity `anonymous` in the filer `Read` on `reports` and `reports-private`, and revokes only the grants that it applied, so a grant that a person adds stays. A person adds each other identity in the admin UI.

#### Scenario: The table row
- **WHEN** a test reads the row `object-store/seaweedfs-s3` of `CLUSTER_SECRETS`
- **THEN** its one entry `s3.json` is the literal `{"identities": []}`, its stack is `infra`, and it restarts `deployment/seaweedfs-s3`

#### Scenario: An unsigned request
- **WHEN** a person sends `curl -s -o /dev/null -w '%{http_code}' http://localhost:8333/` in an S3 gateway pod after the push
- **THEN** the answer is 403
