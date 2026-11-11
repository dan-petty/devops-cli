# Proposal: #4550

## Why

#4550: each release changes most of the layers of the runner and Service images, so each node pulls them again. 5 of 7 runner Jobs pulled the image for 51 to 56 s (2026-11-11), and more short pods come with the move of the roadmap jobs. The `Dockerfile` has three causes:

- The `builder` stage copies `src/` before `uv sync`, so a change of `src/` installs all dependencies again. The `runner` stage builds on `builder`, so all its layers change too.
- The `service` stage copies the whole venv from `builder` in one layer.
- `ci.yml` and `release.yml` build the `service` and `runner` stages with `no-cache-filters`, so each build runs every instruction of those stages again, the install of the dev dependencies included.

Each release also changes the project version in `pyproject.toml` and `uv.lock` (`extra-files` of `release-please-config.json`), so a dependency layer that copies `uv.lock` builds again on each release.

## What Changes

- A new `lock` stage exports the runtime and the dev requirements of `uv.lock`, with their hashes and without the project. A release gives the same two files.
- `deps` holds uv, gh and the venv of the runtime requirements. `builder` builds on it and installs the project with `uv sync --locked --no-dev --no-editable`, then OpenSpec. `runner-tools` installs promtool.
- `runner-deps` and `service-deps` hold all the dependency layers: the apt packages, the Node runtime, gh, the user, the git configuration, the tool directory and the venv. A change of `src/` or of the version keeps them.
- `runner` and `service`, which no build caches, add only the apt upgrade and the project: the `devops_cli` package, its dist-info and `bin/devops`, in one `COPY --parents`.
- Each uv install mounts the uv cache, so no layer holds it. The runner no longer deletes the uv cache and npm, because no stage under it holds them.
- The item does not add a wheel directory with `UV_FIND_LINKS`: it cannot give an offline `uv sync` (see Feasibility). #4814 takes the offline venv.
- `k8s/README.md` describes the stages and the layers.

The images are observable, so the change carries a delta: a new capability `container-image-layers`, and the requirements of `roadmap-implement-runner` and `roadmap-service-deployment` that name the old stages.

The change fits one pull request.

## Capabilities

- `container-image-layers` (new): the lock export, the dependency stages and the final stages.
- `roadmap-implement-runner` (modified): the runner image holds its tools through `runner-deps` and `runner-tools`, and holds no npm, pip or uv cache.
- `roadmap-service-deployment` (modified): the Service image takes OpenSpec and Node through `service-deps`.

## Impact

- A release that changes `src/` and the project version changes one layer of 32 MB in each image, against 1,219 MB of the Service image and 1,747 MB of the runner image before. A node that holds the previous release pulls only that layer.
- The runner image is 2.43 GB (2.50 GB before), because no layer holds the uv cache. The Service image stays at 1.74 GB.
- A build after a change of `src/` does not install the dependencies again: it runs the project install, the tool installs and the two final stages.
- No manifest, no workflow and no command changes. The images keep their paths, users, entry points and tools.

## Feasibility

- The uv Docker guide (https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers, read 2026-11-11) gives the split of the dependency install and the project install, and the cache mount. It does not cover a version change in `uv.lock`; `release-please-config.json` makes that change on each release.
- `ci.yml` and `release.yml` set `no-cache-filters: service` and `no-cache-filters: runner` on the image builds, so each instruction of those stages runs again on each build.
- `COPY --parents` works with `# syntax=docker/dockerfile:1`, and `uv export --locked` runs with no network from `pyproject.toml` and `uv.lock` alone (local BuildKit v0.34.2, uv 0.13.6).
- Measured with local BuildKit builds of `service` and `runner` with `--no-cache-filter`, as CI builds them: build A from `main`, build B with a one-line change of `src/`, and build C with that change and version 9.9.9 in `pyproject.toml` and `uv.lock`. The layers of B and of C that A lacks (uncompressed sizes of `docker history` for the layer digests of `docker image inspect` that differ): 31.8 MB of the Service image and 31.9 MB of the runner image in each case. On `main`, a change of `src/` gave 1,218.7 MB of new layers of 1,361.6 MB in the Service image and 1,746.9 MB of 1,933.0 MB in the runner image. There, the re-run `COPY` of the unchanged `node` binary in the `service` stage also gave a new layer, so the dependency layers must sit in cached stages.
- The old image build ran no uv malware check: `uv sync -vv` next to `pyproject.toml` sent no request to OSV in the image, and neither does `uv pip sync`.
- The wheel directory fails as written (uv 0.13.6, `RUN --network=none`). `UV_FIND_LINKS=<dir> uv sync --locked --offline` stops with "Network connectivity is disabled, but the requested data wasn't found in the cache: https://files.pythonhosted.org/...", because uv installs a locked package from the URL in `uv.lock`. `--no-index --find-links <dir>` resolves again for every platform and fails on `pywin32`. A read-only uv cache in the image fails with "Could not acquire lock ... Read-only file system (os error 30)". A uv cache that the pod copies into its writable cache works: copy 9 s, then offline sync 2 s, cache 852 MB. So this change leaves the two offline-venv criteria to #4814, with this evidence on #4550.

## Existing Tool Considered

uv (`uv export`, `uv pip sync`, `uv pip install --require-hashes`, `uv sync --no-editable` and the cache mount of its Docker guide) and BuildKit (the content key of a `COPY --from` cache, `COPY --parents` and cache mounts) cover the need. The change builds no code. It deletes the second `uv sync` of the runner stage, the `rm -rf` of `/root/.cache/uv`, npm and the npm link in the runner stage, and the copy of the whole venv from `builder`. A pre-pull DaemonSet treats the symptom, and the issue keeps it for a pull that stays over 10 s after this change.
