# Design

## Context

`devops sandbox logs` reads a sandbox container's log through `DockerEngineService.container_log_stream`, and `sandbox/engine.py` turns each `(stdout, stderr)` frame into log lines with their stream. The panic detector reads those lines in order, so a traceback on stderr keeps the stdout lines before it.

## Decision

`container_log_frames(client, container, *, tail, timestamps, follow)` in `docker/engine.py` sends `GET /v<api_version>/containers/<id>/logs` through `client.api.get(..., stream=True)`, with the query that the SDK's `logs` sends. It returns a generator of `(stdout, stderr)` frames:

- no TTY (`attrs["Config"]["Tty"]` is false): read an 8-byte header from `response.raw`, then the frame's bytes, and give `docker.utils.socket.demux_adaptor(stream, data)`; stop at the end of the reply;
- a TTY: give each chunk of `response.iter_content()` as stdout.

The request goes out before the generator is returned, so a refused request fails in `container_log_stream`, which reports it as `Container log stream failed`. The generator closes the reply when it ends or is closed.

`EngineApi` (`docker/sdk.py`) names the parts of the SDK client's session that the read uses: `base_url`, `api_version`, `timeout` and `get`.

## Rejected alternatives

- **`attach(logs=True, stream=..., demux=True)`.** It keeps the streams apart, but it has no `tail` and no `timestamps` (`ContainerApiMixin.attach(self, container, stdout=True, stderr=True, stream=False, logs=False, demux=False)`), and with `stream=False` it waits until a running container stops. `devops sandbox logs --tail` and `--timestamps` would stop working.
- **Two `logs` calls, one for each stream.** Each call keeps `tail`, `timestamps` and `follow`, but the two replies lose the order between the streams that the engine stored, and the panic detector needs it. A merge by timestamp would need `timestamps` on both calls and a second loop for `follow`.
- **The SDK's private helpers** (`APIClient._get`, `_url`, `_read_from_socket`, `_get_raw_response_socket`). They have no stable interface, and `_read_from_socket` reads the raw socket under urllib3, which does not work for a log reply.
- **`docker.utils.socket.frames_iter` on `response.raw`.** It polls the socket's file descriptor and reads it with `os.read`, so it misses the bytes that urllib3 already holds and reads the chunked framing as data.
- **python-on-whales or podman-py.** python-on-whales runs the `docker` CLI, which the runners and the Podman host do not have as a binary. podman-py is a second Engine API client for one call. The project uses docker-py for every other engine call.
