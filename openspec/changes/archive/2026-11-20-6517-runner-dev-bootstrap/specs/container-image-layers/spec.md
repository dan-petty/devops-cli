## MODIFIED Requirements

### Requirement: The lock stage writes the requirements of the lock without the project
The `lock` stage of `Dockerfile` SHALL copy only `pyproject.toml` and `uv.lock`, and SHALL write only the runtime requirements of `uv.lock` with the `review` extra, with `uv export --locked --no-dev --no-emit-project`. A release that changes only the project version then gives the same file, and the stages that copy it keep their cache.

#### Scenario: A version change gives the same requirement files
- **WHEN** a person runs `docker buildx build --target lock --output type=local,dest=<dir>` on two commits that differ only in the project version of `pyproject.toml` and `uv.lock`
- **THEN** the files `lock/runtime.txt` of the two outputs are equal, and no output holds another file under `lock/`

### Requirement: A change of the project keeps the dependency layers
Only the `builder` and `runner-builder` stages SHALL copy a file of `src/`, and no stage under the `runner`, `mcp-server` or `service` stage SHALL build on them. `deps` and `runner-deps` SHALL install only `/lock/runtime.txt` from the `lock` stage, with `--require-hashes`. Each `uv sync` and `uv pip` SHALL mount the uv cache of root as a cache mount.

#### Scenario: A change of src/ keeps the layers under the final stage
- **WHEN** a person builds the `runner`, `mcp-server` and `service` targets two times, and the second build follows a change of a file under `src/`
- **THEN** `docker image inspect --format '{{json .RootFS.Layers}}'` gives the same layer digests for the two builds of each image, except the one layer of the project
