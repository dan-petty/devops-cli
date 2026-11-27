# Proposal

## Why

`devops k8s volume move --storage-class longhorn` (#7382) compares the two sides with the digest script `CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT`, which counts every entry. A new volume of a class with an ext4 filesystem, such as `longhorn`, has the directory `./lost+found` that mkfs makes, and a `local-path` volume, a directory on its node, has none. So the destination has one entry more, the metadata digests differ, and the move stops at the compare and undoes its steps (#7414).

## What Changes

- Each `find` of the digest script prunes the top-level `./lost+found` on each side. The count of the entries uses `! -path .` in place of `-mindepth 1`, so that each `find` has the same form.
- tar still copies a `lost+found` of the source.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-path-volume-placement`: the comparison of a volume move leaves out the top-level `lost+found`.

## Impact

- Code: `src/devops_cli/config/constants.py`
- Tests: `tests/k8s/test_k8s_volume_move.py`
- Documents: `k8s/README.md` (Move a volume to another node)

## Feasibility

- Read on the homelab, 2026-11-27: a copy of a test claim from `local-path` to a new `longhorn` volume gave `entries 2004` on the source and `entries 2005` on the destination, with equal files, bytes and content digests. A path diff showed only `./lost+found` on the destination.
- GNU find: `-path ./lost+found -prune -o <expression>` skips that directory and all under it, and evaluates the expression for each other entry.

## Existing Tool Considered

The digest script exists. The change adds a prune to its five `find` commands: about 3k tokens and 20 minutes.

## Dependencies

None.
