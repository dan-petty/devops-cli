# Proposal

## Why

`devops k8s image-pins` read the untagged image of a system-upgrade-controller Plan as an image on the `latest` tag, and refused it. The controller pulls such an image with the version of the Plan as its tag. `image_nodes` read a tag only from a `version` key in the same mapping as `image` (the Mattermost form), and a Plan keeps its version in `spec` and its images in `spec.prepare` and `spec.upgrade`. So the required check `K8s` of a homelab pull request that adds the Plans of the k3s document "Automated Upgrades" failed (#7455).

## What Changes

- `image_nodes` gives the untagged image of the `prepare` and `upgrade` spec of a Plan (`apiVersion: upgrade.cattle.io/v1`, `kind: Plan`) the tag `spec.version`, with each `+` replaced by `-`. An image with its own tag or digest keeps it. A Plan with no `spec.version` gives no tag, so the check still refuses the untagged images of a Plan that follows a channel.
- The test of "no tag and no digest" uses `parse_repository_tag` of docker-py for both forms, in place of a string test.
- The change alters the images that the command reads, so it carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-image-pins`: an untagged image of a Plan takes the version of the Plan.

## Impact

- Code: `src/devops_cli/k8s/image_pins.py`
- Tests: `tests/k8s/test_image_pins.py`
- Documents: `docs/CLUSTER.md` (Image Pins)
- The change fits one pull request.

## Feasibility

Read in the source of rancher/system-upgrade-controller v0.21.1:

- `pkg/upgrade/handle_upgrade.go:72-81`: when `Spec.Version` is set, `Status.LatestVersion` is `MungeVersion(Spec.Version)`, and the channel is not read. Only a Plan with no version resolves its channel (`ResolveChannel`, line 96), when it runs.
- `pkg/upgrade/plan/plan.go:100-102`: `MungeVersion` replaces each `+` with `-`.
- `pkg/upgrade/job/job.go:330` and `:470`: the `prepare` and the `upgrade` container get `WithLatestTag(plan.Status.LatestVersion)`.
- `pkg/upgrade/container/container.go:46-62`: `WithLatestTag` adds the tag only when `reference.IsNameOnly` is true, so an image with a tag or a digest keeps it.

The Plans of the homelab pull request name `rancher/k3s-upgrade` with `version: v1.37.2+k3s1`, so the controller pulls `rancher/k3s-upgrade:v1.37.2-k3s1`.

## Existing Tool Considered

No open tool gives the image that a Plan of system-upgrade-controller pulls; the check exists and reads the render. The change uses `parse_repository_tag` of docker-py, which the module already uses through `image_reference`, and deletes the string test of a tag and a digest in `image_nodes`. The build cost is about 8k tokens and 30 minutes.
