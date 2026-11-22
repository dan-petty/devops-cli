# Proposal: #6760

## Why

`.devcontainer/Dockerfile`, `Dockerfile` and `.github/workflows/rule-pack.yml` pin `ghcr.io/dan-petty/devtools:20261119`. Since 2026-11-20 the devtools tags have the form `<date>.<run>`, such as `20261122.53`. The Dependency Dashboard (#6030) offers only the tag `20261120`: Renovate does not compare a tag of 2 numbers with the pinned tag of 1 number. The tag `20261122.53` adds `make` (dan-petty/devtools#33), which each commit in dan-petty/homelab needs for its pre-commit hooks.

Closes #6760.

## What Changes

- Pin the three references to `ghcr.io/dan-petty/devtools:20261122.53` at its index digest `sha256:abe82fb0…d4467b1` (amd64 and arm64).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The group `devtools` of `.github/renovate.json` holds both Dockerfiles and the workflow, as before.

## Impact

The devcontainer, the runner image and the rule-pack job use the devtools image of 2026-11-22. After the merge and the devcontainer image build, a person rebuilds the devcontainer.

## Feasibility

`skopeo list-tags docker://ghcr.io/dan-petty/devtools` lists `20261120.41`, `20261121.44` and `20261122.53`. `skopeo inspect` of `20261122.53` gives the revision label 584cef078 (the merge of dan-petty/devtools#34) and the index digest above.

## Existing Tool Considered

Renovate, which keeps the pin current. A pin of the new tag form lets it compare the next tags.
