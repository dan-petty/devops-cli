## ADDED Requirements

### Requirement: The store declares the platform buckets with their quotas
The render of `k8s/object-store` SHALL hold a `Bucket` in namespace `object-store` for `reports` (20Gi), `reports-private` (20Gi), `cache` (10Gi) and `argo-artifacts` (10Gi). Each `Bucket` SHALL name the `Seaweed` CR `seaweedfs` of namespace `object-store` in `seaweedRef`, and SHALL set `quota.size`, a quota that is not `enforce: false`, and `reclaimPolicy: Retain`.

#### Scenario: The committed buckets
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with the four buckets, their quotas, `reclaimPolicy: Retain` and the store in `seaweedRef`

#### Scenario: A bucket that deletes its data
- **WHEN** `uv run devops ci --check --only k8s` runs the bucket rule on the committed buckets with `reclaimPolicy: Delete` on `cache`
- **THEN** the rule reports a problem that names `Bucket/cache`

#### Scenario: The buckets on the cluster
- **WHEN** a person runs `kubectl -n object-store get buckets.seaweed.seaweedfs.com` after the sync
- **THEN** the four buckets are `Ready` with the quotas of git, and a quota that a person changes with `weed shell` `s3.bucket.quota` goes back to the git value at the next reconcile

### Requirement: Only the report buckets have anonymous read
Only the buckets `reports` and `reports-private` SHALL set `anonymousRead: true`, and no `Bucket` SHALL name the user `anonymous` in `access`. No bucket named `backups-*` SHALL have anonymous access.

#### Scenario: The committed anonymous read
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with `anonymousRead: true` on `reports` and `reports-private` only

#### Scenario: A backup bucket with anonymous read
- **WHEN** `uv run devops ci --check --only k8s` runs the anonymous rule on a fixture bucket `backups-example` with `anonymousRead: true`
- **THEN** the rule reports a problem that names `Bucket/backups-example`

#### Scenario: Anonymous requests on the cluster
- **WHEN** a person puts a test object in `reports` and `cache` with a writer key, and sends an anonymous GET of each object and an anonymous List of `reports` to the S3 gateway
- **THEN** the GET in `reports` returns 200, the List of `reports` returns `AccessDenied`, and the GET in `cache` returns `AccessDenied`

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
- **WHEN** a person runs `kubectl -n object-store get bucketlifecyclepolicies.seaweed.seaweedfs.com -o yaml` after the sync, and on a branch revision with a 1-day expiration rule on prefix `lifecycle-test/` of `cache` puts a test object there and starts a multipart upload
- **THEN** the output holds the rules of git, and after the S3 lifecycle pass of the next day the test object and the incomplete upload are gone

### Requirement: Each writer key works only on its own buckets
Each `S3Policy` of the render SHALL allow actions only on buckets of the render, with no wildcard action or resource and no `Deny`. No bucket SHALL be in the policies of two identities. Each `S3PolicyBinding` SHALL bind an `S3Policy` of the render to `S3Identity` subjects of the render only.

#### Scenario: The committed policies
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with the policy of `devops` on `reports`, `reports-private` and `cache`, and the policy of `argo` on `argo-artifacts`

#### Scenario: A policy on every bucket
- **WHEN** `uv run devops ci --check --only k8s` runs the policy rule on the committed policies with resource `*` in the policy of `argo`
- **THEN** the rule reports a problem that names `S3Policy/argo`

#### Scenario: Two identities on one bucket
- **WHEN** `uv run devops ci --check --only k8s` runs the policy rule on the committed policies with `cache` in the policy of `argo`
- **THEN** the rule reports a problem that names bucket `cache`

#### Scenario: Another bucket on the cluster
- **WHEN** a person sends a signed GET of an object of `reports` with the key of `argo-workflows/object-store-argo`
- **THEN** the answer is `AccessDenied`

### Requirement: Each writer key comes from a pushed Secret through a narrow grant
Each `S3Credentials` of the render SHALL name an `S3Identity` of the render, and SHALL name in `secretRef` a Secret that has a row in `CLUSTER_SECRETS` with its access-key and secret-key fields. The namespace of that Secret SHALL hold a `ResourceReferenceGrant` of the render that admits `S3Credentials` of namespace `object-store` to that Secret. Each grant SHALL name the source namespace by name, and each of its targets SHALL be a Secret by name that an `S3Credentials` names.

#### Scenario: The committed keys and grants
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with `S3Credentials` `devops` on Secret `devops/object-store-devops` and `argo` on Secret `argo-workflows/object-store-argo`, each with its grant

#### Scenario: A credential with no row
- **WHEN** `uv run devops ci --check --only k8s` runs the key rule on a fixture `S3Credentials` whose `secretRef` names Secret `devops/object-store-missing`
- **THEN** the rule reports a problem that names `devops/object-store-missing`

#### Scenario: A grant to every Secret
- **WHEN** `uv run devops ci --check --only k8s` runs the key rule on the committed render with no `name` in the target of the grant of `devops`
- **THEN** the rule reports a problem that names the grant `object-store-credentials` of `devops`

#### Scenario: The credentials on the cluster
- **WHEN** a person runs `kubectl -n object-store get s3credentials.seaweed.seaweedfs.com` after the push of the two Secrets
- **THEN** each credential is `Ready` with the access key of its Secret

### Requirement: The operator watches the store and each writer namespace
`watchNamespaces` of `k8s/object-store/operator-values.yaml` SHALL hold exactly `object-store` and the namespace of each `secretRef` of the render, each once, so the operator reads each Secret and grant of a writer and gets no ClusterRole over every namespace.

#### Scenario: The committed watch scope
- **WHEN** `uv run devops ci --check --only k8s` reads the values and renders `k8s/object-store`
- **THEN** the row passes with `object-store`, `devops` and `argo-workflows`

#### Scenario: A writer namespace the operator does not watch
- **WHEN** `uv run devops ci --check --only k8s` runs the watch rule on values with `watchNamespaces: [object-store]`
- **THEN** the rule reports a problem that names namespace `devops`

#### Scenario: The live operator
- **WHEN** a person runs `kubectl -n object-store get deploy seaweedfs-operator -o jsonpath='{.spec.template.spec.containers[0].args}'` and `kubectl get role -A` after the sync
- **THEN** the arguments hold `--watch-namespaces=` with the three namespaces, and `seaweedfs-operator-manager-role` exists in each of them

### Requirement: The store render holds no reconcile workload
The render of `k8s/object-store` SHALL hold only the kinds `Seaweed`, `Bucket`, `BucketLifecyclePolicy`, `S3Identity`, `S3Policy`, `S3PolicyBinding`, `S3Credentials`, `ResourceReferenceGrant`, `NetworkPolicy` and `PodDisruptionBudget`: no Job, CronJob, Pod, workload or script. The AppProject `homelab` SHALL list the namespace of each object of the render in its destinations.

#### Scenario: The committed render
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with only the kinds of this requirement in `object-store`, `devops` and `argo-workflows`

#### Scenario: A reconcile Job
- **WHEN** `uv run devops ci --check --only k8s` runs the kind rule on the committed render with a fixture `Job` `bucket-reconcile`
- **THEN** the rule reports a problem that names `Job/bucket-reconcile`

#### Scenario: The live namespace
- **WHEN** a person runs `kubectl get jobs,cronjobs -n object-store` after the sync
- **THEN** the command reports no resources

### Requirement: The writer keys have ClusterSecret rows
`CLUSTER_SECRETS` SHALL hold row `devops/object-store-devops` with stack `devops` and row `argo-workflows/object-store-argo` with stack `infra`. Each SHALL hold `accessKey` from the keyring-only key `object_store_<writer>_access_key`, generated as 20 hex characters, and `secretKey` from `object_store_<writer>_secret_key`, generated as `token_urlsafe(30)`, and SHALL restart no workload.

#### Scenario: The table rows
- **WHEN** a test reads the rows of the writer keys in `CLUSTER_SECRETS`
- **THEN** each row has the two required entries with their keyring keys and generators, its stack, and no restart

## MODIFIED Requirements

### Requirement: Every Secret that the store reads has a ClusterSecret row
The `k8s` row SHALL fail when the render of `k8s/object-store` references a Secret, by `credentialsSecret`, `configSecret`, `secretKeyRef`, `secretRef` or `secretName`, that has no row in `CLUSTER_SECRETS`. The Secret is in the namespace that the reference names, else in the namespace of the object.

#### Scenario: The committed references
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes, because `seaweedfs-admin`, `seaweedfs-s3`, `devops/object-store-devops` and `argo-workflows/object-store-argo` have rows

#### Scenario: A reference with no row
- **WHEN** `uv run devops ci --check --only k8s` runs the Secret rule on a fixture CR whose admin names Secret `seaweedfs-missing`
- **THEN** the rule reports a problem that names `object-store/seaweedfs-missing`

#### Scenario: A cross-namespace reference with no row
- **WHEN** `uv run devops ci --check --only k8s` runs the Secret rule on a fixture `S3Credentials` of `object-store` whose `secretRef` names Secret `object-store-missing` in namespace `devops`
- **THEN** the rule reports a problem that names `devops/object-store-missing`

### Requirement: The S3 gateway refuses a request with no identity
Secret `object-store/seaweedfs-s3` SHALL hold key `s3.json` with an identities file that has no identity, and the S3 gateway SHALL read it, so a request with no valid signature is refused, except an anonymous GET of an object of a bucket with `anonymousRead`. The identities of the store come from the `S3Identity` CRs of `k8s/object-store`.

#### Scenario: The table row
- **WHEN** a test reads the row `object-store/seaweedfs-s3` of `CLUSTER_SECRETS`
- **THEN** its one entry `s3.json` is the literal `{"identities": []}`, its stack is `infra`, and it restarts `deployment/seaweedfs-s3`

#### Scenario: An unsigned request
- **WHEN** a person sends `curl -s -o /dev/null -w '%{http_code}' http://localhost:8333/` in an S3 gateway pod after the push
- **THEN** the answer is 403
