# Task: The Release Builds the Service Image for linux/amd64 Only (#1954)

**Issue**: [#1954](https://github.com/dan-petty/devops-cli/issues/1954)
**Scope**: scope/ci
**Feasibility**: On 2026-10-23 the job `Build & Publish Service Image` of release run 39986739145 (v0.3.0) took 9.5 minutes. Its log shows the QEMU setup and a build for `linux/amd64,linux/arm64`. `kubectl get nodes -L kubernetes.io/arch` shows that all four cluster nodes are `amd64`. The pull request check `Service Image` builds `linux/amd64` only and took 2.2 minutes on #1952.

## Description

- [x] **Release workflow** (`.github/workflows/release.yml`): the service image job builds and pushes `linux/amd64` only, and it sets up no QEMU. The arm64 build came with #1570 in v0.2.35.
- [x] **Test** (`tests/test_workflow_contracts.py`): `test_no_image_build_emulates_a_platform` fails when a workflow or a composite action sets up QEMU, or when an image build names a platform other than `linux/amd64`.
- Pending a person: the next release run shows the service image job within the 5-minute build budget.
