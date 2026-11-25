# Proposal: #7205

## Why
The `Runner Image` check averaged 487 s, over the 360 s limit. The job built in a builder container and then sent each image to the Docker Engine as a tar file.

## What Changes
- The `Service Image` and `Runner Image` jobs of `ci.yml` set up no builder container. The builds run in the Docker Engine of the runner.
- The builds read the same registry cache as before. The release does not change.

## Capabilities
- `container-image-layers`: new requirement for where a pull request builds the images.

## Impact
No image changes. The two jobs need a Docker Engine with the containerd image store, which `ubuntu-26.04` has.

## Feasibility
- The log of job 139379783035 shows Docker Engine 29.4.2 with the driver type `io.containerd.snapshotter.v1`.
- In that job the tar transfers took 22, 14 and 77 s, the setup of the builder 9 s and its removal 50 s.

## Existing Tool Considered
The Docker Engine builder is in use already for the smoke stages. The change removes a tool.
