# llm-gateway-database Specification

## Purpose
The LiteLLM gateway keeps its virtual keys in a Postgres database. This capability fixes how that database runs, how the gateway reads its connection, who may reach it, and what the gateway does while it is down.

## Requirements

### Requirement: The gateway database is a CloudNativePG Cluster whose Secret the operator generates
The manifests SHALL define a CloudNativePG `Cluster` `llm-gateway-db` in namespace `llm` with one instance on `local-path` storage, annotated so that Argo CD neither prunes nor deletes it, with superuser access off. The `Cluster` SHALL name no `bootstrap.initdb.secret` and no manifest SHALL hold a Secret for it, so that git holds no password.

#### Scenario: The Cluster keeps its data and names no secret
- **WHEN** a test reads `k8s/llm/gateway-db.yaml`
- **THEN** it holds one `Cluster` with `instances` 1, storage class `local-path`, sync option `Prune=false,Delete=false`, `enableSuperuserAccess` false and no `bootstrap.initdb.secret`, and it holds no Secret and no PersistentVolumeClaim

### Requirement: The gateway reads its connection from the operator's Secret
The gateway Deployment SHALL set `DATABASE_URL` from the `uri` key of Secret `llm-gateway-db-app` with `secretKeyRef`, and no literal value.

#### Scenario: DATABASE_URL has no literal value
- **WHEN** a test reads the gateway Deployment that Kustomize renders from `k8s/llm`
- **THEN** its container sets `DATABASE_URL` from `secretKeyRef` name `llm-gateway-db-app` and key `uri`

### Requirement: The gateway migrates on a read-only root file system
The gateway container SHALL keep `readOnlyRootFilesystem: true` and SHALL set `LITELLM_MIGRATION_DIR` to a path that an `emptyDir` volume mounts read-write. It SHALL have a `startupProbe` that allows at least ten minutes before the liveness probe starts.

#### Scenario: The migration directory is an emptyDir
- **WHEN** a test reads the gateway Deployment
- **THEN** the mount at the value of `LITELLM_MIGRATION_DIR` is not read-only and its volume is an `emptyDir`, and `readOnlyRootFilesystem` is true

#### Scenario: A migrating pod is not killed
- **WHEN** a test reads the `startupProbe` of the gateway container
- **THEN** its path is `/health/liveliness` on port 4000, and its period times its failure threshold is at least 600 seconds

### Requirement: A failed migration ends the start-up
The gateway container SHALL set `ENFORCE_PRISMA_MIGRATION_CHECK` to `"true"`, so that a failed `prisma migrate deploy` ends the process and the restart loop waits for the database, instead of a start on an empty schema.

#### Scenario: The check is on
- **WHEN** a test reads the gateway container
- **THEN** it sets `ENFORCE_PRISMA_MIGRATION_CHECK` to `"true"`

### Requirement: The readiness of the gateway does not depend on the database
The `readinessProbe` of the gateway container SHALL use `/health/liveliness` on port 4000. `/health/readiness` answers 503 while the database is down, and Kubernetes would then remove every gateway pod from the Service, also for the clients of the master key.

#### Scenario: A database outage keeps the pods in the Service
- **WHEN** a test reads the `readinessProbe` of the gateway container
- **THEN** its path is `/health/liveliness` on port 4000

### Requirement: The gateway refuses a key it cannot check
The gateway config SHALL NOT turn on `general_settings.allow_requests_on_db_unavailable`, and SHALL keep `store_model_in_db` off.

#### Scenario: The defaults hold
- **WHEN** a test reads `general_settings` of `k8s/llm/gateway/config.yaml`
- **THEN** `allow_requests_on_db_unavailable` is absent or false, and `store_model_in_db` is false

### Requirement: Only the gateway and the operator reach the database
Policy `llm-gateway-db-perimeter` SHALL admit to the database pods on 5432 only the gateway's pods and the CloudNativePG operator (which also uses 8000), and its egress SHALL be DNS and the Kubernetes API only. The gateway's policy SHALL admit egress to the database pods on 5432 by pod selector. `llm-default-perimeter` SHALL leave the database pods out.

#### Scenario: The database perimeter
- **WHEN** a test reads `llm-gateway-db-perimeter`
- **THEN** it selects the pods with `cnpg.io/cluster: llm-gateway-db`, its ingress peers are the pods of `llm-gateway` (5432) and namespace `cnpg-system` (8000 and 5432), and its egress rules cover ports 53 and ports 443 and 6443

#### Scenario: The gateway reaches the database by label
- **WHEN** a test reads `llm-gateway-perimeter`
- **THEN** exactly one egress rule names TCP 5432, and its peer is a pod selector on `cnpg.io/cluster: llm-gateway-db`

#### Scenario: The default perimeter leaves the database out
- **WHEN** a test reads `llm-default-perimeter`
- **THEN** its pod selector excludes pods with `cnpg.io/cluster: llm-gateway-db`
