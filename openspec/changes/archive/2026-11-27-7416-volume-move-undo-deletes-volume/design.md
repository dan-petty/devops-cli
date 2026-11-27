# Design

## Decisions

- **Read the volume in the undo.** The run knows the new volume only after the destination pod is Ready, but a class with `Immediate` binding makes it at the create of the claim. The undo reads `spec.volumeName` of `<claim>-move` when it runs, so it finds the volume at every point.
- **Always set `Delete` before the delete of the claim.** The move made this volume, and it holds only a copy. A patch to `Delete` of a volume that has it already changes nothing.

## Rejected alternatives

- **Delete the PersistentVolume object.** With `Retain`, a delete of the object leaves the volume of the storage system, such as the Longhorn volume and its replicas.
