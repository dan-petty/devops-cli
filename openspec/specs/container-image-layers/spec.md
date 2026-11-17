# container-image-layers Specification

## Purpose
The runner and Service images keep their dependencies in layers that a change of `src/` or a release does not change, so a node that holds the previous release pulls only the small project layer.

## Requirements

### Requirement: The lock stage writes the requirements of the lock without the project
The `lock` stage of `Dockerfile` SHALL copy only `pyproject.toml` and `uv.lock`, and SHALL write the runtime requirements and the dev requirements of `uv.lock` with `uv export --locked --no-emit-project`. A release that changes only the project version then gives the same files, and the stages that copy them keep their cache.

#### Scenario: A version change gives the same requirement files
- **WHEN** a person runs `docker buildx build --target lock --output type=local,dest=<dir>` on two commits that differ only in the project version of `pyproject.toml` and `uv.lock`
- **THEN** the files `lock/runtime.txt` and `lock/dev.txt` of the two outputs are equal

### Requirement: A change of the project keeps the dependency layers
No stage under the `runner` or `service` stage SHALL build on `builder` or copy a file of the build context. `deps` SHALL install `/lock/runtime.txt` and `runner-deps` SHALL install `/lock/dev.txt`, from the `lock` stage, with `--require-hashes`. Each `uv sync` and `uv pip` SHALL mount the uv cache of root as a cache mount.

#### Scenario: A change of src/ keeps the layers under the final stage
- **WHEN** a person builds the `runner` and `service` images two times with `--no-cache-filter runner` and `--no-cache-filter service`, as `ci.yml` and `release.yml` build them, and the second build follows a change of the project version and of a file under `src/`
- **THEN** `docker image inspect --format '{{json .RootFS.Layers}}'` gives the same layer digests for the two builds of each image, up to the last layer of `runner-deps` or `service-deps`

### Requirement: A final stage adds only the apt upgrade and the project
The `runner` and `service` stages SHALL copy from `builder` only the `devops_cli` package, its dist-info and `/app/.venv/bin/devops`, in one `COPY --parents`. They SHALL run `apt-get upgrade` before that copy and SHALL install no apt package.

#### Scenario: The final stage adds the upgrade and one copy of the project
- **WHEN** a person runs `docker history` on a `runner` or `service` image
- **THEN** the layers over those of `runner-deps` or `service-deps` start with the `apt-get upgrade` layer and the one `COPY` layer of `devops_cli`, its dist-info and `devops`
- **AND** `docker run --rm --entrypoint dpkg-query <image> -W -f '${Package}\n'` lists the same packages as the image of `--target runner-deps` or `--target service-deps`
