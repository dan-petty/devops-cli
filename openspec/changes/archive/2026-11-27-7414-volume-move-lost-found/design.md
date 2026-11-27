# Design

## Decisions

- **Leave out only the top-level `lost+found`.** mkfs makes it at the root of a filesystem. A directory with that name lower in the tree is data, so the compare still counts it.
- **Leave it out of the compare, not of the copy.** tar copies a `lost+found` of the source, so the data of an ext4 source stays complete. The compare then does not see files that fsck put there, which are not data of the workload.

## Rejected alternatives

- **Delete `/dst/lost+found` before the copy.** e2fsck uses that directory, and a move must not change the filesystem of the new volume.
