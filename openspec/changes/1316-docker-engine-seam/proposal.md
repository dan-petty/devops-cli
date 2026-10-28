# Proposal

## Why

Issue #1316, a child of #1307 (phase D): `DockerEngineService` is the one way to the Docker engine, but its tests reach past it. The `docker_engine` fixture set the private `_client` of a service and patched `DockerEngineService.get_instance`. `tests/test_docker_engine.py` built 48 `MagicMock` objects and patched `docker.DockerClient` 14 times. No shared fake of the engine existed, and nothing held a double to what the docker SDK does over a real engine.

## What Changes

- `DockerEngineService` builds its SDK client with a `ClientFactory`, `docker.DockerClient` unless `DockerEngineService.install` gives it another. The service still resolves and checks the endpoint first, and still maps a failure to `DockerDaemonUnavailableError` with the endpoint's source.
- `src/devops_cli/docker/sdk.py` names the SDK calls that devops-cli makes as Protocols: the daemon facts, the containers and the container model, the images, the networks, the volumes and the low-level API. `DockerEngineService.client()` returns an `EngineClient`, and `get_container`, `create_container` and `list_images` return the models.
- `tests/support/fakes/docker_engine.py` is an in-memory engine behind the SDK calls, with the `docker_daemon` fixture. It raises the SDK's `NotFound`, `ImageNotFound` and `APIError` with the SDK's own text, refuses a keyword that the SDK's low-level method does not take, can be unreachable, and keeps each call.
- `tests/docker/test_engine_contract.py` runs eight scenarios over the fake and over a real `docker.DockerClient` that reads the Engine API's answers, recorded from Docker Engine 29.9.2 and replayed on a Unix socket that the test binds. A ninth case holds the service's error for an engine that does not answer to the same text over both.
- `tests/test_docker_engine.py` runs on the fake. It builds no `MagicMock` client and reaches no private name of the service. The `docker_engine` factory installs a test's own client through `install` and no longer patches `get_instance`.
- `docs/TESTING.md` describes the seam, the fake and the contract suite.
- The change alters no behavior that a user of `devops` observes, so it has no spec delta and sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/docker/engine.py`, `src/devops_cli/docker/sdk.py` (new).
- Tests: `tests/support/fakes/docker_engine.py`, `tests/support/docker_engine_scenarios.py`, `tests/support/docker_engine_replay.py`, `tests/support/docker_engine_recording.py`, `tests/docker/test_engine_contract.py`, `tests/fixtures/docker_engine/recorded_exchanges.json` (all new); `tests/test_docker_engine.py`, `tests/conftest.py`.
- Documents: `docs/TESTING.md`.

## Feasibility

- On `origin/main` 0137f231, `DockerEngineService` (`src/devops_cli/docker/engine.py`) is the only builder of the SDK client: `commands/docker.py`, `docker/sandbox.py`, `sandbox/engine.py`, `commands/devcontainer.py` and `ui/data_providers.py` reach the engine through `get_engine()`. The dashboard's own `docker.from_env()`, which the issue leaves to #1334, is gone since #1108.
- docker-py 7.2.0, the pinned SDK, reads `GET /version` when `DockerClient` is built with no `version` (`APIClient.__init__`), so an engine that does not answer fails in the constructor. A factory, not an installed client, is what keeps that failure on the service's path.
- docker-py reads an exec's output and a log stream from the socket under the HTTP reader (`_get_raw_response_socket`, `frames_iter`), and a stream of JSON entries only from a chunked reply (`_stream_helper` reads `response.raw._fp.chunked`). A server on a Unix socket that sends `101 UPGRADED` and raw frames, and chunked replies, serves both; the hermetic floor allows a socket that the test binds.
- A local Docker Engine 29.9.2 (API 1.56) recorded the exchanges on 2026-10-28. Every scenario gave the same result over the fake as over the engine before the recording, and the replay serves each scenario with no request outside the record.
- docker-py's `ContainerApiMixin.logs` has no `demux` argument, so `container_log_stream`, which passes `demux=True`, fails on every real engine. The fake refuses the keyword as the SDK does. The defect is #2520; this change does not change the method.
- The issue's last criteria do not apply: #1309 is closed as not planned, so no ceiling exists to lower, and no `unreachable(...)` marker of #1310 names the Docker daemon.
- No open item owns this work: #1325, #1327, #1334 and #1335 move their packages' tests onto this fake later, and #1315 builds the Kubernetes seam.

## Existing Tool Considered

- `responses`, `requests-mock` and `vcrpy` answer HTTP calls at the `requests` or `http.client` layer, but their replies have no socket under the reader and no chunked raw stream, which docker-py reads for an exec, a log stream and a stats stream. Rejected.
- `testcontainers` and `pytest-docker` run a real engine. The tests never use a live daemon (decided 2026-10-07, Q26 of #1307), and CI has none. Rejected.
- docker-py's own `fake_api` lives in its test suite, not in the wheel. Rejected.
- The replay server and the recorder use `h11`, already a dev dependency, for the HTTP framing, and `socketserver` from the standard library.
- Cost of building instead (rule 3): about 600k tokens to build in one session, about 4 hours elapsed; upkeep is a new recording when the docker SDK pin changes, one command of about 2 minutes on a host with a local engine.
- The change deletes the 48 `MagicMock` objects and the 14 patches of `docker.DockerClient` in `tests/test_docker_engine.py`, and the `get_instance` patch of the `docker_engine` fixture.
