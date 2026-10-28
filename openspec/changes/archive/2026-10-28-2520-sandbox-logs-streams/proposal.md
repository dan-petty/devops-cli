# Proposal

## Why

Issue #2520: `devops sandbox logs` cannot read the logs of a sandbox from a real Docker engine. `DockerEngineService.container_log_stream` (`src/devops_cli/docker/engine.py`) calls `container.logs(..., demux=True)`. The docker SDK's `logs` has no `demux` argument, so each call raises `TypeError`, and the service reports `Container log stream failed`. The tests did not see it, because they gave the service a mock client that takes any argument.

## What Changes

- `container_log_stream` reads `GET /containers/{id}/logs` through the SDK client's own HTTP session (`DockerClient.api`, a `requests.Session` with the engine's transport). It sends `stdout`, `stderr`, `timestamps`, `follow` and `tail` as the SDK's `logs` sends them, and gives the reply as `(stdout, stderr)` frames: each frame holds the bytes of one stream, in the order that the engine sent them.
- The reply of a container without a TTY is the Engine API's multiplexed stream. Each frame has an 8-byte header that names its stream and its length. The SDK's own `docker.utils.socket.demux_adaptor` turns the stream number into the `(stdout, stderr)` frame. The reply of a container with a TTY is one raw stream, which the SDK also reads as stdout.
- A refused request fails with the SDK's own error (`docker.errors.create_api_error_from_http_exception`), and the service reports it as `Container log stream failed`, as before.
- With `follow`, the read has no read timeout, as the SDK disables the socket timeout of a followed log. The connect timeout stays the client's timeout.
- The Docker engine fake (#1316) serves the same request from a container's scripted frames, and a contract scenario holds the fake and the real SDK client, over answers recorded from a real engine, to the same lines.
- `tests/test_sandbox_logs.py` reads the logs of the sandbox engine over the fake and gives up its mock clients.
- `devops sandbox logs` changes behavior that a user sees: it reads logs again. The change carries a spec delta, the new capability `sandbox-logs`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `sandbox-logs`: how `devops sandbox logs` reads a sandbox container's log, with the stream of each line.

## Impact

- `src/devops_cli/docker/engine.py`, `src/devops_cli/docker/sdk.py`.
- `tests/support/fakes/docker_engine.py`, `tests/support/docker_engine_scenarios.py`, `tests/docker/test_engine_contract.py`, `tests/fixtures/docker_engine/recorded_exchanges.json`, `tests/test_sandbox_logs.py`.

## Feasibility

- docker 7.2.0, the locked SDK: `ContainerApiMixin.logs(self, container, stdout=True, stderr=True, stream=False, timestamps=False, tail='all', since=None, follow=None, until=None)` has no `demux`. Only `attach` and `exec_start` take `demux`, and they read a hijacked socket (`_read_from_socket`).
- The SDK reads a log reply with `_multiplexed_response_stream_helper` or `_multiplexed_buffer_helper` (`docker/api/client.py`). Both unpack each frame header as `_, length = struct.unpack('>BxxxL', header)` and drop the stream number. So no `logs` call of the SDK keeps the two streams apart.
- `docker.utils.socket.frames_iter` reads a raw socket with `select.poll` and `os.read`. It cannot read a log reply, because urllib3 holds the reply's buffer and its chunked framing above the socket.
- Docker documents the multiplexed stream in the Engine API reference ("Stream format", `ContainerAttach`): an 8-byte header `[STREAM_TYPE, 0, 0, 0, SIZE1, SIZE2, SIZE3, SIZE4]`, where stream type 1 is stdout and 2 is stderr, and no header when the container has a TTY.
- A local Docker Engine 29.9.2 (API 1.56) on 2026-10-28: `container.logs(..., demux=True)` raised `TypeError: ContainerApiMixin.logs() got an unexpected keyword argument 'demux'`, as the issue records. The new contract scenario was recorded from the same engine: the frames of a container that writes one line to each stream came back with their stream, with `tail`, `timestamps` and `follow`.

## Existing Tool Considered

The docker SDK (docker-py 7.2.0) is the open tool that covers the Engine API, and the change keeps it: the SDK client's session sends the request, the SDK's `demux_adaptor` names each frame's stream, and the SDK's `create_api_error_from_http_exception` makes the error. The SDK has no public call that reads a log with its streams apart, so the change adds one loop of about ten lines that reads each frame header (`struct.Struct(">BxxxL")`) from the reply.

Written cost of the loop: about 150k tokens to build it with its tests and recording, about 5k tokens a year to keep it (the stream format has not changed since API 1.24), and about 10k tokens and one hour to replace it with the SDK call if docker-py adds `demux` to `logs`. Elapsed time to build: about two hours.

Deleted: the `demux=True` call of `container.logs` in `container_log_stream`, and the five mock clients of `tests/test_sandbox_logs.py` that scripted `container.logs`.
