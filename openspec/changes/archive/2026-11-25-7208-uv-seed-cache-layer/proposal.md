# Proposal: #7208

## Why
Each release changes the version in `pyproject.toml` and `uv.lock`. The seed copied both and `src/` before `uv sync`, so each release installed all dependencies again and pushed a new cache layer, although no dependency changed.

## What Changes
- The `lock` stage also exports the dev requirements, and a stub project with the build backend of `pyproject.toml`.
- The cache layer of the seed is built from those two only. Only `seed.json` reads `uv.lock`.

## Capabilities
- `container-image-layers`: the requirement of the uv seed names its inputs and a stable cache layer.

## Impact
A release builds the seed's cache layer from cache and keeps its digest. The cache holds the same packages, and a stub project in place of `devops-cli`.

## Feasibility
- In release run 45664435299 the sync ran again, the layer export took 32 s, the push 25 s and the cache export 44 s.
- With Podman, a change of the project version builds the cache layer from cache with the same digest.
- `uv-seed-smoke` syncs the checkout from the new seed with no network. The image has the size of the published one, 1.18 GB.

## Existing Tool Considered
`uv export`, `uv pip sync` and BuildKit's cache of `COPY --from` cover the need, and the other images use them.
