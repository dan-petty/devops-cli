# Tasks

## 1. The service builds its SDK client through a factory

- [x] Add failing tests: the engine tests build `DockerEngineService(fake.client_factory)` and read the factory's arguments, and the contract suite's unreachable case compares the service over the SDK and over an unreachable fake
  - Verification: `uv run devops ci test tests/test_docker_engine.py tests/docker/test_engine_contract.py`
- [x] Add the Protocols of `src/devops_cli/docker/sdk.py`, the `ClientFactory` and `DockerEngineService.install`, and type `client()` and the container and image returns
  - Verification: `uv run devops ci typecheck`

## 2. An in-memory engine fake and its contract suite

- [x] Add the contract suite and its scenarios, the recorded-answer server and the recorder
  - Verification: `uv run devops ci test tests/docker/test_engine_contract.py`
- [x] Add `DockerEngineFake` and the `docker_daemon` fixture, and record the scenarios from a local engine
  - Verification: `uv run devops ci test tests/docker/test_engine_contract.py`
- [x] Describe the seam, the fake and the contract suite in `docs/TESTING.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. The engine's tests run on the fake

- [x] Move `tests/test_docker_engine.py` onto the fake, with no `MagicMock` client and no private name of the service, and install the `docker_engine` factory's client through `install`
  - Verification: `uv run devops ci test tests/test_docker_engine.py tests/test_docker.py tests/test_sandbox_lifecycle.py tests/test_sandbox_logs.py tests/test_ui_dashboard.py`

## 4. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 1316-docker-engine-seam`

## Workflow follow-up

- #2520: `container_log_stream` passes `demux` to the SDK's `logs`, which does not take it.
- #1325, #1327, #1334 and #1335 move the tests of their packages from the `docker_engine` factory to `docker_daemon`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
