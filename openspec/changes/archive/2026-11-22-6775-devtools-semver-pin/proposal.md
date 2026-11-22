# Proposal: #6775

## Why

`.devcontainer/Dockerfile`, `Dockerfile` and `.github/workflows/rule-pack.yml` pin `ghcr.io/dan-petty/devtools:20261122.53` (#6760). dan-petty/devtools#37 moved the image to semantic versions, and its first release `v1.0.0` published the tags `1.0.0`, `1.0`, `1` and `latest`. Renovate does not compare the tag `20261122.53` with `1.0.0`, so it offers no update.

Closes #6775.

## What Changes

- Pin the three references to `ghcr.io/dan-petty/devtools:1.0.0` at its index digest `sha256:3dae8696…b8668f3d` (amd64 and arm64).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The group `devtools` of `.github/renovate.json` holds the three references, as before.

## Impact

The devcontainer, the runner image and the rule-pack job use the devtools release `1.0.0`. Renovate then offers each new devtools release and each new digest of the daily rebuild.

## Feasibility

`skopeo list-tags docker://ghcr.io/dan-petty/devtools` lists `1.0.0`, `1.0`, `1` and `latest`. `skopeo inspect` of `1.0.0` gives the version label `1.0.0`, the revision label 00ec5fcd6 (the release commit of dan-petty/devtools) and the index digest above.

## Existing Tool Considered

Renovate, which keeps the pin current once the pin has the semantic version form.
