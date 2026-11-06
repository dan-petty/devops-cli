# Proposal

## Why

The row `release_comments` checks the images of each release in its window (#3507). A new release has no image until its build ends, about 6 minutes after the release is published. Until then the registry answers HTTP 404 for the tag. The row counts that normal state as a failed round. In one day, Loki showed 9 such rounds and 1 suspension after 3 rounds in a row. Each 404 was on a release that was less than 5 min 30 s old. A 404 on the newest release also stops the check of the older releases, so their `Live since` comments come late.

`tag_digest` raises a plain `RegistryReadError` for each status, so a caller cannot tell a missing tag from another read error.

## What Changes

- `tag_digest` raises the new `RegistryTagNotFoundError` on HTTP 404. It is a subclass of `RegistryReadError`, so `check_pins` in `src/devops_cli/argo/image_pins.py` keeps its `except RegistryReadError`. Each other status raises `RegistryReadError`.
- `live_release` takes the time of the round (`now`). When a tag of a release gives `RegistryTagNotFoundError` and the release is less than `CONST_ROADMAP_RELEASE_IMAGE_GRACE_MINUTES` (20) old, the walk skips that release and checks the older ones. At or past that age, the error propagates, and the row fails as before. This covers the `service` and the `runner` tag.
- The new error has its own code, `DOCKER_REGISTRY_TAG_NOT_FOUND`, and a row in `docs/ERRORS.md`.
- `k8s/README.md` states the rule for the row.
- The change has a spec delta: the row is behavior of the Service, and the error code of a missing tag changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-release-comments`: a missing tag of a new release is "not yet".
- `argo-image-pin-drift`: the registry read raises `RegistryTagNotFoundError`, a `RegistryReadError`, for a missing tag.

## Impact

- Code: `src/devops_cli/docker/registry.py`, `src/devops_cli/exceptions/docker.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/roadmap/release_roll.py`, `src/devops_cli/roadmap/release_comments.py`, `src/devops_cli/config/constants.py`.
- Documents: `docs/ERRORS.md` (generated), `k8s/README.md`.
- Tests: `tests/docker/test_registry_tag_digest.py`, `tests/roadmap/test_roadmap_release_roll.py`, `tests/roadmap/test_roadmap_release_comments.py`, `tests/roadmap/test_roadmap_run.py`.
- The change fits one pull request.

## Feasibility

- On `origin/main` (dc9815e6), `tag_digest` raises `RegistryReadError(...)` for each status other than 200 (`src/devops_cli/docker/registry.py`). Before the change, the new tests for the 404 case fail: the import of the new error fails.
- `live_release` walks `releases` in the order given, newest first (`for release in releases`), and `_digest` raises at the first 404. `_live_pass` catches `RegistryReadError` and returns each waiting tag, so `comment_releases` raises `RoadmapRunError`. The new round tests failed on that code with `RoadmapRunError ... could not check the images of 2 release(s): v1.1.0, v1.0.0`.
- The release publish time is `ReleaseInfo.published_at`, which the code already reads for the window. `comment_releases` already takes `now` as a parameter, so the age needs no new API call and no new clock.
- The build time comes from the issue: release workflow run 41861187135 published v0.55.4 at 15:46:32Z, and the images ended at 15:52:12Z and 15:52:36Z (about 6 min 4 s).

## Existing Tool Considered

No library covers the need: the change extends `tag_digest` and `RegistryReadError` of `src/devops_cli/docker/registry.py` with one subclass, one branch and one age check. The code already reads the registry with the project HTTP client, and it only needs to tell HTTP 404 from the other statuses. Cost: about 10,000 tokens to build, about 2,000 tokens a year to keep, and about 2 hours elapsed. The change deletes no internal code.
