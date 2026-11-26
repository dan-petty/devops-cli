## REMOVED Requirements

### Requirement: The object-store namespace is restricted and kept
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The operator Application installs a supported chart before the store
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The store Application deploys the store after the operator
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The store runs a supported SeaweedFS release
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Three masters keep the control state
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Three volume servers hold the data on three nodes
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Two filers and two S3 gateways serve the objects
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The admin and the worker maintain the store with signed writes
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The optional APIs of the store stay off
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The S3 gateway refuses a request with no identity
**Reason**: The row is a row of `cluster-secrets.toml` of the environment tree, and the gateway is in the environment repository (#7290).
**Migration**: The environment repository declares the row.

### Requirement: The admin UI refuses a request with no password
**Reason**: The row is a row of `cluster-secrets.toml` of the environment tree (#7290).
**Migration**: The environment repository declares the row.

### Requirement: The store pods stay off the control-plane node
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Only the worker reaches the admin gRPC port
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The store has no internet egress
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Clients reach the S3 port by a namespace label
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Alloy reaches the metrics port of each component
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Each store workload is restricted, budgeted and scraped
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Every Secret that the store reads has a ClusterSecret row
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: No manifest holds fs.mergeVolumes
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: No Ingress host serves an internal port of the store
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The store requests at most one CPU and 3 GiB of memory
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: deploy-stack installs the store with stack infra
**Reason**: Moved: this change adds the product behavior to another capability (#7290).
**Migration**: See the requirement of the same name in `k8s-helm-deploy`.

### Requirement: The store alerts on its five failure conditions
**Reason**: The environment repository holds this alert rule and its cases (#7290).
**Migration**: Change the rule in the environment repository.

### Requirement: The build test proves the S3 clients
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The build test proves the gateways, a volume loss and the admin port
**Reason**: `k8s/README.md` of devops-cli describes the product base and the commands only (#7290).
**Migration**: The README of the environment repository describes its own services.

### Requirement: The store declares the platform buckets with their quotas
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: One CR makes each bucket
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Only the report buckets have anonymous read
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: Each bucket has its lifecycle rules in git
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The operator watches only the store namespace
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: The store render holds no reconcile workload
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.

### Requirement: No key rows in the ClusterSecret table
**Reason**: Moved: this change adds the product behavior to another capability (#7290).
**Migration**: See `The product Secret table holds no key of the object store` of `cluster-secrets-loader`.
