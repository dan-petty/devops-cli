# Design

## Decisions

- **Two builds in one composite action**: The Dev Containers CLI adds Feature layers after the last stage of the Dockerfile. We split the build into two steps inside `.github/actions/devcontainer-image/action.yml`: Dev Containers CLI builds target `base` with Features, then `docker buildx build` adds `project` on top of that digest.
- **Default `BASE_IMAGE=base` in `.devcontainer/Dockerfile`**: Setting `ARG BASE_IMAGE=base` before `FROM` lets a single `docker build` without arguments default to building the complete image with local `base`.
- **Target project digest for smoke test, attestation, and tags**: Downstream steps in `release.yml` and `devcontainer-image.yml` consume the action output `digest`, which points to the final project build image.
- **Registry cache configuration**: Pass `cache-from` to both builds and `cache-to` only to the Feature build. Feature layers stay cached when only `src/` changes.

## Rejected alternatives

- **Wait for or depend on external issue**: #6414 is closed; the current tree layout can deliver the layer order directly.
- **Install features directly in Dockerfile**: Bypassing Dev Containers CLI loses `devcontainer.metadata` labels and duplicates upstream feature installation logic.
- **Two separate workflow jobs with digest passing via artifact**: Adds workflow complexity, artifact overhead, and an extra job when one action step sequence suffices.
