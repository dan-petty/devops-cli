# Design

## Context

See proposal.md for defect background and motivation.
The locked docker-py 7.2.0 library exposes individual resource collections on `DockerClient` (`containers`, `networks`, `images`, `volumes`).
Each collection provides a `prune(filters=None)` method returning a dictionary representation of the Engine API prune response.

## Goals / Non-Goals

**Goals:**
- Provide a robust `prune` method on `DockerEngineService` executing collection prunes in correct dependency order.
- Calculate and report total reclaimed megabytes accurately.
- Convert daemon errors to `DockerEngineError` and surface cleanly without tracebacks.
- Provide specced client doubles in the test suite to prevent attribute regressions.

**Non-Goals:**
- Clear BuildKit build cache during prune: `devops docker cache --prune` manages build cache.
- Prune tagged images via an `--all` flag: only dangling images are pruned.

## Decisions

### 1. Encapsulate prune logic in `DockerEngineService`
- Decision: Add `prune(self, *, volumes: bool = False) -> int` to `DockerEngineService` in `src/devops_cli/docker/engine.py`.
- Rationale: Encapsulates API error handling and disk usage cache invalidation alongside `prune_build_cache`.
- Alternative considered: Call docker-py collections directly from `src/devops_cli/commands/docker.py`.
  - Rejected: Command layer should not manage SDK exception wrapping or internal cache invalidation.

### 2. Prune sequence and filter configuration
- Decision: Sequentially call `containers.prune()`, `networks.prune()`, `images.prune()`, and conditionally `volumes.prune()` with default `filters=None`.
- Rationale: Removing stopped containers first unlocks networks and dangling images attached to them.
- Alternative considered: Call in reverse or arbitrary order.
  - Rejected: Removing networks before containers fails when stopped containers still attach to those networks.

### 3. Reclaimed space aggregation
- Decision: Parse `SpaceReclaimed` from each dictionary response, defaulting missing or non-integer values to 0.
- Rationale: Networks prune responses do not provide `SpaceReclaimed`, and container/image responses return byte integers.
- Alternative considered: Parsing tuple responses.
  - Rejected: docker-py collection prune methods return dictionaries directly from engine JSON responses.

### 4. Strongly typed and autospecced test doubles
- Decision: Define `docker_client` fixture in `tests/conftest.py` using `create_autospec(docker.DockerClient, instance=True)` and specced collection instances.
- Rationale: Plain `MagicMock` permitted arbitrary method calls such as `client.system.prune`, hiding defects in test execution.
- Alternative considered: Rely on manual attribute mocking.
  - Rejected: Fails to detect missing attributes or changed argument signatures in future updates.

## Risks / Trade-offs

- [Engine returns unexpected response format] -> Graceful extraction treats missing or null `SpaceReclaimed` keys as 0 bytes.
- [Interrupted prune sequence on error] -> First encountered error raises `DockerEngineError` immediately and aborts remaining operations.
