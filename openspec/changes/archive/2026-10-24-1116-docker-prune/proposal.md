# Proposal

## Why

Issue #1116: `devops docker prune` fails on every engine because it calls `client.system.prune(volumes=volumes)`.
In docker-py 7.2.0, `DockerClient` has no `system` attribute, which causes an `AttributeError` traceback.
Existing tests used unconstrained `MagicMock` clients and pinned an unreturned tuple format, masking the defect.

## What Changes

- Add a `prune` method to `DockerEngineService` in `src/devops_cli/docker/engine.py`.
- Call `containers.prune()`, `networks.prune()`, and `images.prune()` in that order without filters.
- Call `volumes.prune()` when `--volumes` is set.
- Sum `SpaceReclaimed` values from dictionary responses, treating missing or null values as zero.
- Invalidate the engine disk usage cache after pruning.
- Catch daemon errors, wrap them in `DockerEngineError`, and exit 1 with one error line and no traceback.
- Update `devops docker prune` in `src/devops_cli/commands/docker.py` to call the new service method and remove the tuple return branch.
- Update command help, confirmation prompt, and option help in `src/devops_cli/lang/en/help.py` and `src/devops_cli/commands/docker.py`.
- Add an autospecced `docker_client` fixture in `tests/conftest.py`.
- Update tests in `tests/test_docker.py` to use `docker_client` and add prune coverage.
- Update knowledge base documentation in `src/devops_cli/ai/knowledge_base/it_domains/tools/docker.md`.
- Regenerate CLI reference documentation with `devops docs generate --sync-readme`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `docker-prune`: Clean up stopped containers, unused networks, dangling images, and optionally unused volumes through docker-py collection prune calls.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/docker/engine.py`: Implements `DockerEngineService.prune`.
- `src/devops_cli/commands/docker.py`: Updates `prune` command implementation and confirmation prompt.
- `src/devops_cli/lang/en/help.py`: Updates help strings for `prune` and `--volumes`.
- `tests/conftest.py`: Provides autospecced `docker_client` fixture.
- `tests/test_docker.py`: Uses `docker_client` fixture and tests prune behaviors.
- `src/devops_cli/ai/knowledge_base/it_domains/tools/docker.md`: Updates knowledge base command description.
- `docs/commands/docker.md`: Regenerated command reference.

## Feasibility

- Inspected `docker.DockerClient` in python with docker-py 7.2.0: `hasattr(docker.DockerClient, "system")` evaluates to `False`.
- Inspected collection classes in `docker.models`: `ContainerCollection`, `NetworkCollection`, `ImageCollection`, and `VolumeCollection` all expose `prune(filters=None)`.
- Verified `create_autospec(docker.DockerClient, instance=True)` combined with specced collections raises `AttributeError` on `client.system` and `TypeError` on invalid arguments.

## Existing Tool Considered

The change uses the official `docker-py` collection prune methods provided by the existing locked dependency `docker==7.2.0`.
No new library is required.
Deleted internal code includes the unreachable tuple result parser in `src/devops_cli/commands/docker.py`.
