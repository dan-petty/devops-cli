# Design

## Decisions

- The rule reads only an object with `apiVersion: upgrade.cattle.io/v1` and `kind: Plan`, and only the `image` of its `spec.prepare` and `spec.upgrade` mappings. These are the two containers that get `WithLatestTag` (`pkg/upgrade/job/job.go:330` and `:470` of v0.21.1).
- `spec.version` decides, also when the Plan sets `channel` too: the controller reads the channel only when the version is empty (`pkg/upgrade/handle_upgrade.go:72`).
- One test of "no tag and no digest", `parse_repository_tag` of docker-py, serves the Mattermost form and the Plan form. It is the split of the Docker reference grammar that `image_reference` already uses.

## Rejected alternatives

- A tag from any `version` key in the object, for any image of it. Rejected: the controller tags only the `prepare` and `upgrade` containers (`job.go:330`, `:470`), and a `version` key in another object, such as a CRD schema, is no tag.
- A version tag in the images of the homelab Plans. Rejected in #7455: Renovate would then move 4 image tags in the `-k3s` form and 3 version values in the `+k3s` form in one branch, which needs a group across two datasources and a second parity rule.
- A read of the channel to get the tag of a Plan with no version. Rejected: `ResolveChannel` (`pkg/upgrade/plan/plan.go:109`) gives the tag when the Plan runs, and the channel moves it later, so no tag at merge time names the image that a node pulls.
