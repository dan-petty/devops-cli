# Design

## Decisions

- **pv-migrate does the copy, and the command keeps its own steps around it.** pv-migrate copies one claim to another claim. It does not pause Argo CD, stop the workloads, rebind the claim name or undo a move. So the plan, the pause and the end of the running syncs, the scale to zero, the `Retain` patches, the save and the delete of the old claim, the rebind, the start and the undo stay.
- **The strategy is `clusterip` only.** The default list of pv-migrate starts with `mount`, which puts both claims in one pod. With no pod on either claim, pv-migrate sets no node affinity, and the scheduler puts that pod on the node of the old local-path volume, so local-path binds the new volume on the old node. `clusterip` puts the sshd pod with the old claim on its node and the rsync pod with the new claim on the node that `rsync.nodeSelector` names.
- **The values go on stdin.** `--helm-values -` gives one JSON document with the node selector and the tolerations, so no temporary file holds them, and the dry run prints them as the stdin of the request.
- **The move names the pv-migrate operation.** `--id volume-move-<8 hexadecimal digits>` fits the limit of 24 characters, and the undo of a stopped copy runs `pv-migrate cleanup <operation> --force`.
- **`--non-root` only in a namespace that enforces `restricted`.** As root, rsync keeps the owner and the group of each file. `--non-root` keeps neither, so the move uses it only where Pod Security refuses root. There the workload reads the files through its `fsGroup`, so the plan refuses a workload with no `fsGroup`, and a class whose provisioner is not a CSI driver or whose CSIDriver has `fsGroupPolicy: None`. The plan reads the class of the old claim for a move that keeps the class.
- **The rebind of the claim name stays.** The issue asks whether the new claim name can go to git in place of the `claimRef` rebind. A claim of `volumeClaimTemplates`, such as `llm/qdrant-storage-qdrant-0`, gets its name from the StatefulSet, so git cannot give it another name. A Deployment would need a pull request between the copy and the start, with Argo CD paused all that time. So the rebind stays, and with it the pause.
- **No compare after the copy.** rsync computes a checksum of each file that it sends and sends the file again on a difference. pv-migrate fails the move when rsync exits with an error (`waitForRsyncJob`). The compare of #7414 also gave false differences (`lost+found` of a new ext4 volume).
- **The copy measure goes.** `volume_move_measure` measured the tar pipe of #3695 and #7408, which no longer exists. pv-migrate has its own integration tests across two kind clusters (`integration/integration_test.go`).

## Claims that can move to Longhorn

Read from dan-petty/homelab `main` at `c8ec227`, `k8s/README.md` (Replicated Volumes) and the manifests that name `local-path` or `fast-nvme`:

| Claim | Class now | Path |
| --- | --- | --- |
| `llm/open-webui-data`, `llm/qdrant-storage-qdrant-0`, `llm/valkey-data`, `llm/valkey-runs-data` | `longhorn` | Moved. A Longhorn volume has two copies on two nodes, so it needs no move to another node. |
| `monitoring/prometheus-server`, `monitoring/grafana`, `monitoring/storage-prometheus-alertmanager-0` | `longhorn` | Moved. |
| `devops/valkey-data-roadmap`, `devops/renovate-cache`, `devops/roadmap-service-home` | `longhorn` | Moved. |
| The claims of Pyroscope (`monitoring`), Tempo (`otel`) and Loki (`logging`) | `local-path` | `devops k8s volume move <namespace>/<claim> --storage-class longhorn` after the class change in git, with the StatefulSet deleted with `--cascade=orphan`, as for Qdrant. `otel` enforces `restricted`, so the plan there asks for an `fsGroup`. |
| `mattermost/mattermost-files` | `local-path` | The Mattermost operator owns the Deployment and scales it back, so the command cannot stop it. A move needs the operator stopped first. |
| The CloudNativePG clusters `mattermost-db` and `llm-gateway-db` | `local-path` | The plan refuses a pod that a CloudNativePG `Cluster` owns. CloudNativePG moves the data itself, with a new instance on the new class. |
| The volumes of `object-store` (SeaweedFS) | `fast-nvme` | Stay. The class keeps them on the NVMe of the control-plane node. |

The move of these claims belongs to the storage work of dan-petty/homelab. This change does not change that repository.

## Rejected alternatives

- **Longhorn in place of pv-migrate.** A CSI clone (`dataSource` of a claim) works only within one driver, and Longhorn cannot read a local-path directory. So a claim needs one copy to get on `longhorn`, and pv-migrate does that copy. After it, Longhorn removes the need for a move between nodes. A claim that stays on `local-path` or `fast-nvme` still needs the copy.
- **Velero (Apache-2.0, v1.19.0).** It backs up a claim to object storage and restores it with another class. That needs a backup location and a restore of the namespace objects, for one claim, and the data goes out of the cluster and back.
- **The default strategies of pv-migrate (`mount,clusterip,loadbalancer`).** See the `clusterip` decision: `mount` binds the new local-path volume on the old node.
- **`--non-root` in each namespace.** It gives up the owner and the group of each file also where Pod Security allows root, and a workload without an `fsGroup` then cannot write its data.
- **A user and a group of the workload for the pv-migrate pods (`--helm-set rsync.securityContext.runAsUser=<uid>`).** The rsync and sshd images of v3.8.0 have only the user `pvmigrate` (10000) in `/etc/passwd` (`docker/rsync/Dockerfile`, `docker/sshd/Dockerfile`), and OpenSSH needs a user entry for its uid.
- **`pv-migrate cleanup` in each undo of the copy.** After a run that pv-migrate ended itself, nothing is left, and `cleanup` exits 1 with `no releases found for operation`, so each such undo would report a false failure.
- **`pv-migrate cleanup --all --namespace <namespace>`.** It exits 0 with nothing left, but it also removes the operation of another person in the namespace.
- **VolSync.** AGPL-3.0, not a permissive license.
