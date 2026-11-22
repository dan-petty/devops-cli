## ADDED Requirements

### Requirement: The store declares the platform buckets with their quotas
The render of `k8s/object-store` SHALL hold a `Bucket` in namespace `devops` for `reports` (20Gi), `reports-private` (20Gi) and `cache` (10Gi), and a `Bucket` in namespace `argo-workflows` for `argo-artifacts` (10Gi). Each `Bucket` SHALL name the `Seaweed` CR `seaweedfs` of namespace `object-store` in `clusterRef`, and SHALL set `quota.size`, a quota that is not `enforce: false`, and `reclaimPolicy: Retain`.

#### Scenario: The committed buckets
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with the four buckets in their namespaces, their quotas, `reclaimPolicy: Retain` and the store in `clusterRef`

#### Scenario: A bucket that deletes its data
- **WHEN** `uv run devops ci --check --only k8s` runs the bucket rule on the committed buckets with `reclaimPolicy: Delete` on `cache`
- **THEN** the rule reports a problem that names `Bucket/cache`

#### Scenario: A bucket in the store namespace
- **WHEN** `uv run devops ci --check --only k8s` runs the bucket rule on the committed buckets with `cache` in namespace `object-store`
- **THEN** the rule reports a problem that names `Bucket/cache`

#### Scenario: The buckets on the cluster
- **WHEN** a person runs `kubectl get buckets.seaweed.seaweedfs.com -A -o yaml` after the sync
- **THEN** the output has `reports` 20Gi, `reports-private` 20Gi and `cache` 10Gi in namespace `devops` and `argo-artifacts` 10Gi in namespace `argo-workflows`, each `Ready` with `reclaimPolicy: Retain` and a `clusterRef` to `object-store/seaweedfs`, and a quota that a person changes with `weed shell` `s3.bucket.quota` goes back to the git value at the next reconcile

### Requirement: One grant admits the buckets to the store
The render SHALL hold a `ResourceReferenceGrant` in namespace `object-store` that admits each `Bucket` of the render outside `object-store` to the `Seaweed` CR `seaweedfs`. Each grant of the render SHALL be in `object-store`, SHALL admit only the kind `Bucket` of group `seaweed.seaweedfs.com` from a namespace of a `Bucket` of the render, named by name and not by a selector, and SHALL admit it only to the `Seaweed` CR `seaweedfs` by name.

#### Scenario: The committed grant
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with one grant that admits the buckets of `devops` and `argo-workflows` to `seaweedfs`

#### Scenario: A bucket namespace with no grant
- **WHEN** `uv run devops ci --check --only k8s` runs the grant rule on the committed render with `argo-artifacts` in namespace `llm`
- **THEN** the rule reports a problem that names `Bucket/argo-artifacts`

#### Scenario: A grant to every Seaweed CR
- **WHEN** `uv run devops ci --check --only k8s` runs the grant rule on the committed render with no `name` in the target of the grant
- **THEN** the rule reports a problem that names the grant `object-store-buckets`

#### Scenario: The grant on the cluster
- **WHEN** a person runs `kubectl get buckets.seaweed.seaweedfs.com -A -o jsonpath='{.items[*].status.conditions}'` after the sync
- **THEN** no bucket has the condition `ClusterRefForbidden` with status `True`

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

### Requirement: The operator watches the store and each bucket namespace
`watchNamespaces` of `k8s/object-store/operator-values.yaml` SHALL hold exactly `object-store` and the namespace of each `Bucket` and `BucketLifecyclePolicy` of the render, each once, so the operator reconciles each bucket and its rules and gets no ClusterRole over every namespace.

#### Scenario: The committed watch scope
- **WHEN** `uv run devops ci --check --only k8s` reads the values and renders `k8s/object-store`
- **THEN** the row passes with `object-store`, `devops` and `argo-workflows`

#### Scenario: A bucket namespace the operator does not watch
- **WHEN** `uv run devops ci --check --only k8s` runs the watch rule on values with `watchNamespaces: [object-store]`
- **THEN** the rule reports a problem that names namespace `devops`

#### Scenario: The live operator
- **WHEN** a person runs `kubectl -n object-store get deploy seaweedfs-operator -o jsonpath='{.spec.template.spec.containers[0].args}'` and `kubectl get role -A` after the sync
- **THEN** the arguments hold `--watch-namespaces=` with the three namespaces, and `seaweedfs-operator-manager-role` exists in each of them

### Requirement: The store render holds no reconcile workload
The render of `k8s/object-store` SHALL hold only the kinds `Seaweed`, `Bucket`, `BucketLifecyclePolicy`, `ResourceReferenceGrant`, `NetworkPolicy` and `PodDisruptionBudget`: no Job, CronJob, Pod, workload or script. The AppProject `homelab` SHALL list the namespace of each object of the render in its destinations.

#### Scenario: The committed render
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with only the kinds of this requirement in `object-store`, `devops` and `argo-workflows`

#### Scenario: A reconcile Job
- **WHEN** `uv run devops ci --check --only k8s` runs the kind rule on the committed render with a fixture `Job` `bucket-reconcile`
- **THEN** the rule reports a problem that names `Job/bucket-reconcile`

#### Scenario: The live namespace
- **WHEN** a person runs `kubectl get jobs,cronjobs -n object-store` and `kubectl get pods -n object-store -o jsonpath='{.items[*].spec.containers[*].image}'` after the sync
- **THEN** the first command reports no resources, and the second lists only the SeaweedFS images of the store and the operator

### Requirement: No key rows in the ClusterSecret table
`CLUSTER_SECRETS` SHALL hold no row for a key of the store: no row whose name starts with `object-store-`. The key pair of a writer comes from an ESO `Password` generator of the tenant chart, not from the keyring.

#### Scenario: The table rows
- **WHEN** a unit test reads `CLUSTER_SECRETS` in `src/devops_cli/k8s/cluster_secrets.py`
- **THEN** no row has a name that starts with `object-store-`
