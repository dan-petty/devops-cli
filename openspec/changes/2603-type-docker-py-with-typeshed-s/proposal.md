# Proposal

## Why

docker-py 7.2.0 ships no type hints, so nine imports in src carry # type: ignore[import-untyped] markers. The src type: ignore ceiling sits at 51, its value, so new code cannot import docker-py's reference parser. This blocks #1997 from using docker-py's parse_repository_tag and resolve_repository_name, forcing a 10-line hand-rolled split in registry.py. Adding typeshed's types-docker stubs removes the nine markers, frees ceiling budget, and lets registry.py use the typed parser. See #2603.

## What Changes

- Add types-docker==7.2.0.20261006 to the dev dependency group in pyproject.toml
- Narrow the except clause at engine.py line 261 from Exception to requests.HTTPError
- Align the Protocol member types in sdk.py with the types-docker stubs so DockerClient satisfies EngineClient
- Keep one # type: ignore[import-untyped] on the get_current_context_name import in engine.py
- Remove the 8 now-unused # type: ignore[import-untyped] markers from engine.py, sandbox/host.py, and commands/docker.py
- Lower DEFAULT_SUPPRESSION_CEILINGS['src type: ignore'] from 51 to 42 in tests/test_architectural_invariants.py
- Replace the hand-rolled reference split in tagged_image with docker.utils.parse_repository_tag and docker.auth.resolve_repository_name
- Add a spec delta to argo-image-pin-drift: tagged_image now resolves references without a registry host to the default registry docker.io instead of raising RegistryReadError
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `argo-image-pin-drift`: tagged_image splits reference with docker-py parser

## Impact

- Code: `pyproject.toml`, `src/devops_cli/docker/engine.py`, `src/devops_cli/docker/sdk.py`, `src/devops_cli/sandbox/host.py`, `src/devops_cli/commands/docker.py`, `src/devops_cli/docker/registry.py`
- Tests: `tests/test_architectural_invariants.py`

## Feasibility

- The 9 # type: ignore[import-untyped] markers are visible in src/devops_cli/docker/engine.py at the imports of docker, docker.errors, docker.utils, docker.constants, docker.transport, and docker.context.api.
- The ceiling value of 51 is stated in the issue body and confirmed by the test in tests/test_architectural_invariants.py.
- The 3 mypy errors (line 261, 315, 393) are stated in the issue body, measured on 2026-10-29 with the stubs installed.
- The hand-rolled split in tagged_image is visible in src/devops_cli/docker/registry.py lines 55-68.
- First check: uv sync installs types-docker and uv run mypy src reports the 9 unused ignores and 3 new errors.
- Second check: uv run pytest tests/docker/test_registry_tag_digest.py confirms the table tests pass before the parser change.

## Existing Tool Considered

typeshed's types-docker (7.2.0.20261006) provides type stubs for docker-py 7.2.0. It lacks docker.context.api.get_current_context_name, which requires one remaining type: ignore marker. Nothing new is built; the change deletes 8 ignores and the 10-line hand-rolled split in registry.py.
