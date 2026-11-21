---
status: proposed
date: 2026-11-21
decision-makers: [owner]
issue: 4750
tracker: 4742
---

# The object store is SeaweedFS with its operator

## Context and Problem Statement

The cluster has no object store. The off-node backups of the Gitea data (#2144) and of the gateway database (#3741), the project review reports and later the artifacts of Argo Workflows need an S3 target that keeps a copy of each object on a node other than its source node. The 19 `local-path` volumes of the cluster have no backup. The owner asks for a permissive license (decision 1 of #4742, `CONTRIBUTING.md`), and the cluster has 3 worker nodes with NVMe disks and 1 control-plane node.

## Considered Options

- **SeaweedFS with the SeaweedFS operator** (both Apache-2.0): masters, volume servers, filers and a standalone S3 gateway, with replication across volume servers. The operator makes every workload from one `Seaweed` CR, and its Helm chart ships the CRDs. Chosen.
- **Garage**: AGPL-3.0, which the license rule refuses. Rejected.
- **MinIO**: AGPL-3.0, which the license rule refuses. Rejected.
- **Ceph RGW**: LGPL, and it needs raw devices and the operation of a Ceph cluster. Rejected.
- **RustFS**: it needs 4 nodes or more, and its contributor agreement allows a relicense. Rejected.
- **versitygw**: it has no replication. Rejected.
- **s3proxy**: it has no lifecycle rules. Rejected.
- **Apache Ozone and CubeFS**: 4 or 5 service types to run for one store. Rejected.

## Decision Outcome

Chosen option: "SeaweedFS with the SeaweedFS operator", because it is the one permissive, maintained store that replicates across 3 nodes, and the operator removes each hand-written workload.

- One `Seaweed` CR in namespace `object-store` (`k8s/object-store/seaweed.yaml`) gives 3 masters with Raft, 3 volume servers (one on each node, replication `001`), 2 filers with leveldb2, 2 standalone S3 gateways, 1 admin and 1 worker. The Argo CD Application `seaweedfs-operator` installs the operator chart before the Application `object-store` applies the CR, and `devops k8s deploy-stack --stack infra` does the same without Argo CD.
- The release rule has no minimum release age: the pin is the newest SeaweedFS release that the newest operator release builds against, never under 4.53 and never 4.48 to 4.51. `spec.image` pins it by digest. The `k8s` row of `devops ci` refuses a release or a chart under the floor.
- The perimeter, the Secrets and the closed APIs answer the advisories with no fix: only the worker reaches the admin gRPC port (GHSA-3qr2-qw48-cj6q), the admin has a password (GHSA-m3m8-mrgq-hf9h), and the S3 gateway runs with the IAM subsystem, the Iceberg catalog and the Lance namespace off (GHSA-25hp-4mw7-9c75). The gateway reads an identities file, so it refuses each request until an identity exists.
- A client namespace opts in with the label `backup-client: "true"`, so no rule of the store names a service.

### Confirmation

`uv run devops ci --check --only k8s` holds the layout, the release floor, the perimeter, the Secret gate and the closed APIs. The build test of `k8s/README.md` (Object Store, Build test) proves the store on the cluster with boto3 and minio-go uploads, a read through the second gateway, the loss of one volume pod and the admin port.

## Consequences

- Good, because each object has a second copy on another node, and the loss of one node loses no object.
- Good, because the operator makes the StatefulSets, the Services, the ServiceMonitors and the JWT keys, so the repository holds no workload of the store.
- Bad, because the store has its own release rule: a Renovate pull request of the image waits for the operator release that builds against it.
- Bad, because the store needs 3 Ready nodes that are not the control-plane node, so a cluster with fewer nodes, such as minikube, cannot run it.
- Neutral, because the general settings of the operator, a platform stack that any service can use, move to dan-petty/infra in a later item ([ADR 0032](0032-infrastructure-templates-live-in-four-homes.md)).
