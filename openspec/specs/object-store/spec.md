# object-store Specification

## Purpose
The object store of the cluster is SeaweedFS, which the SeaweedFS operator deploys from one `Seaweed` CR in namespace `object-store`. This capability fixes its versions, its layout, its perimeter, its Secrets, its deploy path, its alerts and the checks of the `k8s` row that hold them.

## Requirements

### Requirement: The object-store namespace is restricted and kept
Namespace `object-store` in `k8s/namespaces.yaml` SHALL enforce Pod Security `restricted` and SHALL carry the sync option `Prune=false,Delete=false`.

#### Scenario: The committed namespace
- **WHEN** `uv run devops ci --check --only k8s` renders the root kustomization
- **THEN** the row passes with namespace `object-store` at `restricted` with `Prune=false,Delete=false`

#### Scenario: A namespace with no restricted label
- **WHEN** `uv run devops ci --check --only k8s` runs the namespace rule on a fixture namespace `object-store` with no `pod-security.kubernetes.io/enforce` label
- **THEN** the rule reports a problem that names Namespace `object-store`

### Requirement: The operator Application installs a supported chart before the store
The Argo CD Application `seaweedfs-operator` SHALL use project `homelab`, the chart `seaweedfs-operator` of `https://seaweedfs.github.io/seaweedfs-operator` at 0.1.47 or newer, destination namespace `object-store`, sync-wave `-1` and `ServerSideApply=true`, and its values SHALL set no operator image tag, so the operator is the `appVersion` of the chart.

#### Scenario: The committed operator Application
- **WHEN** `uv run devops ci --check --only k8s` reads `k8s/argocd/apps/seaweedfs-operator.yaml`
- **THEN** the row passes with project `homelab`, the SeaweedFS repository, a chart of 0.1.47 or newer, namespace `object-store`, sync-wave `-1` and server-side apply

#### Scenario: A chart under the floor
- **WHEN** `uv run devops ci --check --only k8s` runs the chart rule on a fixture Application whose chart is 0.1.46
- **THEN** the rule reports a problem that names the floor 0.1.47

### Requirement: The store Application deploys the store after the operator
The Argo CD Application `object-store` SHALL deploy `k8s/object-store` in project `homelab` to namespace `object-store` with a sync-wave greater than `-1` and `SkipDryRunOnMissingResource=true`. The AppProject `homelab` SHALL list the SeaweedFS chart repository in `sourceRepos` and namespace `object-store` in its destinations.

#### Scenario: The committed store Application and project
- **WHEN** `uv run devops ci --check --only k8s` reads `k8s/argocd/apps/object-store.yaml` and `k8s/argocd/apps/projects.yaml`
- **THEN** the row passes with path `k8s/object-store`, project `homelab`, a sync-wave greater than `-1`, the repository in `sourceRepos` and the namespace in the destinations

### Requirement: The store runs a supported SeaweedFS release
The `Seaweed` CR SHALL pin `spec.image` to `chrislusf/seaweedfs` with a release tag of 4.53 or newer and a `sha256` digest, SHALL NOT pin a release from 4.48 to 4.51, and no component SHALL set its own `version`.

#### Scenario: The committed release
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with a digest-pinned release of 4.53 or newer

#### Scenario: An excluded release
- **WHEN** `uv run devops ci --check --only k8s` runs the release rule on the fixture image `chrislusf/seaweedfs:4.48@sha256:<digest>`
- **THEN** the rule reports a problem that names release 4.48 and the range 4.48 to 4.51

### Requirement: Three masters keep the control state
The `Seaweed` CR SHALL run 3 masters with replication `001`, `volumeSizeLimitMB` 1000, the volume growth `copy_2 = 2`, the argument `-telemetry=false` and a claim for the Raft state of each master.

#### Scenario: The committed masters
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with 3 masters, replication `001`, `volumeSizeLimitMB` 1000, `copy_2 = 2`, `-telemetry=false` and a master claim

#### Scenario: The master command line
- **WHEN** a person runs `kubectl -n object-store get pod seaweedfs-master-0 -o jsonpath='{.spec.containers[0].command}'` after the sync
- **THEN** the command holds `-telemetry=false`

### Requirement: Three volume servers hold the data on three nodes
The `Seaweed` CR SHALL run 3 volume servers on `fast-nvme` claims with a required hostname anti-affinity among the volume pods, `maxVolumeCounts` 300 and `minFreeSpacePercent` 10.

#### Scenario: The committed volume servers
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with 3 volume servers, `fast-nvme` claims, the hostname anti-affinity, `maxVolumeCounts` 300 and `minFreeSpacePercent` 10

### Requirement: Two filers and two S3 gateways serve the objects
The `Seaweed` CR SHALL run 2 filers with a leveldb2 store on a claim and no S3 in the filer, and the standalone S3 gateway with 2 replicas on port 8333.

#### Scenario: The committed filers and gateways
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with 2 leveldb2 filers on claims, no filer S3 and 2 S3 replicas on 8333

### Requirement: The admin and the worker maintain the store with signed writes
The `Seaweed` CR SHALL run 1 admin with `credentialsSecret` `seaweedfs-admin`, 1 worker with the job types `vacuum`, `volume_balance`, `admin_script` and `s3_lifecycle` and no erasure coding, and JWT signing for volume and filer writes.

#### Scenario: The committed admin, worker and signing
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with the admin Secret, the four job types, no erasure coding and `volumeWrite` and `filerWrite` signing

### Requirement: The optional APIs of the store stay off
The S3 gateway SHALL set `iam: false` and the arguments `-port.iceberg=0` and `-port.lance=0`, and SHALL name a `configSecret`. The filer SHALL NOT turn on S3, Iceberg or Lance. The CR SHALL set no `sftp` and no `vector`, and no component SHALL pass `-iam.config` or `-webdav`.

#### Scenario: The committed CR
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with the IAM API, Iceberg, Lance, SFTP, S3 Vectors and the filer S3 off

#### Scenario: A filer with the Iceberg catalog
- **WHEN** `uv run devops ci --check --only k8s` runs the feature rule on a fixture CR with `filer.iceberg.enabled: true`
- **THEN** the rule reports a problem that names the Iceberg catalog of the filer

### Requirement: The S3 gateway refuses a request with no identity
Secret `object-store/seaweedfs-s3` SHALL hold key `s3.json` with an identities file that has no identity, and the S3 gateway SHALL read it, so a request with no valid signature is refused, except an anonymous GET of an object of a bucket with `anonymousRead`. The identities of the store come from the `S3Identity` CRs of `k8s/object-store`.

#### Scenario: The table row
- **WHEN** a test reads the row `object-store/seaweedfs-s3` of `CLUSTER_SECRETS`
- **THEN** its one entry `s3.json` is the literal `{"identities": []}`, its stack is `infra`, and it restarts `deployment/seaweedfs-s3`

#### Scenario: An unsigned request
- **WHEN** a person sends `curl -s -o /dev/null -w '%{http_code}' http://localhost:8333/` in an S3 gateway pod after the push
- **THEN** the answer is 403

### Requirement: The admin UI refuses a request with no password
Secret `object-store/seaweedfs-admin` SHALL hold `adminUser` (the literal `admin`) and `adminPassword` (the keyring-only key `seaweedfs_admin_password`, made with `token_urlsafe(32)` when the keyring lacks it), with stack `infra`, and it SHALL restart `statefulset/seaweedfs-admin`.

#### Scenario: The table row
- **WHEN** a test reads the row `object-store/seaweedfs-admin` of `CLUSTER_SECRETS`
- **THEN** it holds the two entries of this requirement, and `seaweedfs_admin_password` is a keyring-only key

#### Scenario: No password
- **WHEN** a person sends `curl -s -o /dev/null -w '%{http_code}' http://localhost:23646/` through `kubectl -n object-store port-forward svc/seaweedfs-admin 23646` with no credential
- **THEN** the answer is 401, 403 or a redirect to `/login`, never 200

### Requirement: The store pods stay off the control-plane node
Each component of the `Seaweed` CR that has a claim SHALL set the required node affinity `node-role.kubernetes.io/control-plane` `DoesNotExist`, and its claims SHALL use the storage class `fast-nvme`.

#### Scenario: The committed placement
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with the exclusion on the masters, the volume servers and the filers, and `fast-nvme` on each claim

#### Scenario: A volume server with no exclusion
- **WHEN** `uv run devops ci --check --only k8s` runs the placement rule on a fixture CR whose volume affinity has no control-plane exclusion
- **THEN** the rule reports a problem that names `Seaweed/seaweedfs` and the component `volume`

### Requirement: Only the worker reaches the admin gRPC port
The NetworkPolicies of namespace `object-store` SHALL admit to the admin pod on TCP 33646 only the worker pods, and SHALL let only the worker pods send to it. No egress rule of these policies SHALL cover the port for another pod, also with no `ports`, so the port stays closed if a policy gets both types again: the controller of the cluster then skips its ingress rules for that traffic. The ingress rules hold for other namespaces.

#### Scenario: The committed perimeter
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes, a filer pod, the operator pod and a pod of another namespace get no ingress rule to 33646 of the admin pod, no pod of the namespace other than the worker gets an egress rule to it, and the worker gets both

#### Scenario: A perimeter that admits a filer
- **WHEN** `uv run devops ci --check --only k8s` runs the perimeter rule on a fixture policy that admits the filer pods on 33646
- **THEN** the rule reports a problem that names the policy and port 33646

#### Scenario: A perimeter whose in-namespace egress has no ports
- **WHEN** `uv run devops ci --check --only k8s` runs the perimeter rule on the committed policies with no `ports` in the in-namespace egress rule of `object-store-perimeter-egress`
- **THEN** the rule reports a problem that names `object-store-perimeter-egress` and port 33646

#### Scenario: A policy that lets a filer send to the admin port
- **WHEN** `uv run devops ci --check --only k8s` runs the perimeter rule on a fixture policy that lets the filer pods send to the admin pod on 33646
- **THEN** the rule reports a problem that names the policy and port 33646

#### Scenario: A worker with no egress to the admin port
- **WHEN** `uv run devops ci --check --only k8s` runs the perimeter rule on the committed policies without `object-store-worker`
- **THEN** the rule reports that no policy lets the worker send to the admin pod on 33646

#### Scenario: The live port
- **WHEN** a person runs `nc -z -w 3 seaweedfs-admin 33646` in a filer pod and in the worker pod
- **THEN** the filer pod cannot connect and the worker pod connects

### Requirement: The store has no internet egress
The NetworkPolicies of namespace `object-store` SHALL admit egress only to CoreDNS and to the pods of the namespace, except that the operator pod reaches the Kubernetes API on 6443 with the metadata address excluded.

#### Scenario: The committed egress
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with no egress rule to an address block, except the API rule of the operator pod

#### Scenario: A perimeter with internet egress
- **WHEN** `uv run devops ci --check --only k8s` runs the egress rule on a fixture policy of every pod with egress to `0.0.0.0/0`
- **THEN** the rule reports a problem that names the policy

### Requirement: Clients reach the S3 port by a namespace label
The perimeter SHALL admit each namespace with the label `backup-client: "true"` to TCP 8333 of the S3 gateway, and no rule SHALL name a client namespace by its name.

#### Scenario: The committed client rule
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with a namespace selector on `backup-client: "true"` for port 8333 and no `kubernetes.io/metadata.name` selector but those of `kube-system` and `monitoring`

### Requirement: Alloy reaches the metrics port of each component
The egress of the NetworkPolicies of namespace `monitoring` SHALL let the `alloy-metrics` pod send to namespace `object-store` on the metrics port of each component, and the perimeter of the store SHALL admit the pod on that port.

#### Scenario: The committed perimeters
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/monitoring` and `k8s/object-store`
- **THEN** the row passes with an egress rule of `monitoring-default-perimeter-egress` to namespace `object-store` on 9327 and an ingress rule of the store from namespace `monitoring` on 9327

#### Scenario: A monitoring perimeter with no egress to the store
- **WHEN** `uv run devops ci --check --only k8s` runs the scrape rule on the monitoring policies with the egress rule to `object-store` removed
- **THEN** the rule reports a problem that names `monitoring-default-perimeter-egress`

### Requirement: Each store workload is restricted, budgeted and scraped
Each component of the `Seaweed` CR SHALL set a pod security context with `runAsNonRoot`, a non-root `runAsUser` and `seccompProfile` `RuntimeDefault`, and a container security context with `allowPrivilegeEscalation: false` and `capabilities.drop: [ALL]`. Each component and the operator SHALL have a PodDisruptionBudget. Each component SHALL set a `metricsPort`, and `spec.serviceMonitor.enabled` SHALL be true, so the operator makes a ServiceMonitor for each component.

#### Scenario: The committed workloads
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store`
- **THEN** the row passes with the security contexts, one budget for each of `master`, `volume`, `filer`, `s3`, `admin`, `worker` and the operator, a metrics port on each component and the ServiceMonitors on

#### Scenario: The live pods
- **WHEN** a person runs `kubectl -n object-store get pods,pdb,servicemonitors -o wide` after the sync
- **THEN** 3 master, 3 volume, 2 filer, 2 s3, 1 admin, 1 worker and 1 operator pods are Running, the 3 volume pods are on 3 nodes, each budget selects its pods, and each component has a ServiceMonitor

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

### Requirement: No manifest holds fs.mergeVolumes
The `k8s` row SHALL fail when the render of an Argo CD path Application or a values file of `k8s/object-store` holds the text `fs.mergeVolumes`, because `seaweedfs/seaweedfs#12521` can lose a completed object.

#### Scenario: The committed renders
- **WHEN** `uv run devops ci --check --only k8s` renders each path Application
- **THEN** the row passes with no `fs.mergeVolumes`

#### Scenario: An admin script with the command
- **WHEN** `uv run devops ci --check --only k8s` runs the field rule on a fixture `AdminScript` whose script holds `fs.mergeVolumes`
- **THEN** the rule reports a problem that names `fs.mergeVolumes` and the object

### Requirement: No Ingress host serves an internal port of the store
No component of the `Seaweed` CR SHALL turn on an Ingress, the CR SHALL set no `hostSuffix`, and no Ingress of a path Application SHALL route to Service `seaweedfs-master`, `seaweedfs-volume`, `seaweedfs-filer` or `seaweedfs-admin`.

#### Scenario: The committed renders
- **WHEN** `uv run devops ci --check --only k8s` renders each path Application
- **THEN** the row passes with no Ingress for the master, volume, filer or admin ports

#### Scenario: The live Ingresses
- **WHEN** a person runs `kubectl get ingress -A` after the sync
- **THEN** no Ingress names a host for those four Services

### Requirement: The store requests at most one CPU and 3 GiB of memory
The CPU requests and the memory requests of the components of the `Seaweed` CR, each times its replicas, with the requests of the operator values, SHALL add up to at most 1 CPU and 3Gi.

#### Scenario: The committed requests
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/object-store` and reads `k8s/object-store/operator-values.yaml`
- **THEN** the row passes with a sum of at most 1 CPU and 3Gi

### Requirement: deploy-stack installs the store with stack infra
`devops k8s deploy-stack --stack infra` SHALL add the chart repository `seaweedfs-operator`, SHALL install release `seaweedfs-operator` into namespace `object-store` after release `cert-manager`, and SHALL apply `object-store` after the charts. No other stack SHALL list the release.

#### Scenario: The stack tables
- **WHEN** a test reads `HELM_REPOS_BY_STACK`, `HELM_RELEASES_BY_STACK` and `POST_HELM_BY_STACK`
- **THEN** stack `infra` holds the repository, the release in `object-store` after `cert-manager`, and the post-Helm path `object-store`, and no other stack holds the release

### Requirement: The store alerts on its five failure conditions
The `seaweedfs` group of `serverFiles.alerting_rules.yml` SHALL hold `SeaweedFSNoLeader`, `SeaweedFSUnderReplicatedVolumes`, `SeaweedFSVolumeServerDown`, `SeaweedFSReadOnlyVolumes` and `SeaweedFSVolumeDiskLow`, each with a row in the alert table of `k8s/README.md`, and the SeaweedFS dashboard SHALL be in a ConfigMap of the dashboard generator with the label `grafana_dashboard: "1"`.

#### Scenario: The rules and the dashboard
- **WHEN** `promtool check rules` runs on the rule files of the server, `devops grafana dashboards lint` runs on `k8s/monitoring/dashboards/seaweedfs.json`, and `uv run devops ci --check --only k8s` renders `k8s/monitoring`
- **THEN** promtool accepts the group, the lint finds no problem, and the row passes

### Requirement: The build test proves the S3 clients
The build test of `k8s/object-store/build-test/` SHALL run 4 parallel 150 MB multipart uploads with boto3 and one streaming upload of unknown size with minio-go through Service `seaweedfs-s3`, from a namespace with the label `backup-client: "true"`. The README section `Build test` SHALL make the bucket `build-test` before the Jobs start, because the identity `build-test` has the actions Read, Write, List and Tagging and SeaweedFS authorizes a bucket create as `Admin`.

#### Scenario: The client uploads
- **WHEN** a person runs the steps of the README section `Build test` after the merge and the push of the Secrets
- **THEN** the log of each Job reports each upload as complete

### Requirement: The build test proves the gateways, a volume loss and the admin port
The README section `Build test` SHALL measure the delay until a key written through one S3 gateway pod shows in `ListObjectsV2` through the other, SHALL PUT and GET an object with one volume pod deleted, and SHALL try TCP 33646 of the admin from a filer pod and from the worker pod.

#### Scenario: The in-cluster checks
- **WHEN** a person runs the steps of the README section `Build test` after the merge and the push of the Secrets
- **THEN** the cross-gateway delay is 10 seconds or less, the PUT and the GET succeed with one volume pod deleted, the filer pod cannot connect to 33646 and the worker pod connects

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
