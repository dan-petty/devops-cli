## Purpose

The runner and Service images keep their dependencies in layers that a change of `src/` or a release does not change, so a node that holds the previous release pulls only the small project layer.

## ADDED Requirements

### Requirement: The lock stage exports the requirements without the project
The `lock` stage of `Dockerfile` SHALL copy only `pyproject.toml` and `uv.lock`, and SHALL write the runtime requirements and the dev requirements of `uv.lock` with `uv export --locked --no-emit-project`. A release that changes only the project version then gives the same files, and the stages that copy them keep their cache.

#### Scenario: The lock stage is read offline
- **WHEN** a test reads the `lock` stage of `Dockerfile`
- **THEN** it copies only `pyproject.toml` and `uv.lock`, and its `uv export --locked --no-emit-project` commands write `/lock/runtime.txt` with `--no-dev --extra review` and `/lock/dev.txt` with `--only-dev`

### Requirement: The dependency stages hold no file of the project
No stage under the `runner` or `service` stage SHALL build on `builder` or copy a file of the build context. `deps` SHALL install `/lock/runtime.txt` and `runner-deps` SHALL install `/lock/dev.txt`, from the `lock` stage, with `--require-hashes`. Each `uv sync` and `uv pip` SHALL mount the uv cache of root as a cache mount.

#### Scenario: The stages under a final stage are read offline
- **WHEN** a test reads the stages under `runner` and under `service`
- **THEN** none of them is `builder` or copies from the build context, `deps` and `runner-deps` copy their requirements from `lock` and install them with `--require-hashes`, and every `uv sync` and `uv pip` mounts `type=cache,target=/root/.cache/uv`

### Requirement: A final stage takes only the project from the builder
The `runner` and `service` stages SHALL copy from `builder` only the `devops_cli` package, its dist-info and `/app/.venv/bin/devops`, in one `COPY --parents`. They SHALL run `apt-get upgrade` before that copy and SHALL install no apt package.

#### Scenario: A final stage is read offline
- **WHEN** a test reads the `runner` stage or the `service` stage
- **THEN** its one `COPY --from=builder` is `COPY --from=builder --parents` of the package, the dist-info and the console script to `/`, an `apt-get upgrade` comes before it, and no `RUN` holds `apt-get install`
