# Design

## Decisions

- **The plan keeps the class of the old claim, and adds the target class.** `VolumeMovePlan.storage_class` stays the class of the old claim. The new field `target_storage_class` is empty when the move keeps the class. The property `new_storage_class` gives the class of the move claim and of the claim made again.
- **The nodes that can attach a class come from the CSI objects.** A CSI driver attaches a volume only on a node whose CSINode lists the driver. The plan reads the StorageClass, then the CSIDriver with the name of its provisioner. When that CSIDriver exists, the plan reads the CSINodes and keeps the nodes that list the driver. A provisioner that is not a CSI driver, such as `rancher.io/local-path`, does not limit the nodes. A label of one storage system, such as `node.longhorn.io/create-default-disk`, is not used.
- **The target node can be the node of the old volume.** With a class change, the new volume is not the old one, so a copy on one node is correct and fast.
- **The plan still names one target node.** The destination copy pod selects that node, so the plan and the run print the same node. Without `--to-node`, it is the node with the most free disk of the nodes that can attach the class.
- **The run checks only that the pods run.** A volume of a replicated class does not hold its pod on one node. A pod that cannot reach the new volume does not get to `Running`, so the check still finds a failed start.
- **The size stays the size of the old claim.** local-path does not limit a volume to its size, but a class such as `longhorn` does. When the data does not fit, the copy fails before the point of no return, and the run undoes its steps. The README tells the operator to compare the data with the size before the move.

## Rejected alternatives

- **A new option for the size.** The claim in git holds the size, and Argo CD cannot change it on a `local-path` claim. An option would make the live claim differ from git.
- **No target node for a class change.** The destination pod would then go to any node, and the plan could not name it. The plan prints the node before the run starts.
- **A check of the used bytes in the plan.** The kubelet's `/stats/summary` gives no `usedBytes` for a `local-path` volume (read on the homelab, 2026-11-27), so the plan cannot read them without a pod on the volume.
