# Design

## Decisions

### The seam is the SDK client, built by a factory

The fake stands in for `docker.DockerClient`, not for `DockerEngineService`. The service's endpoint resolution and check, its projections into typed models, its response cache and its mapping of SDK errors then run for real in every test, and the dashboard's calls (`info`, `containers.list`, `images.list`, `networks.list`, `volumes.list`) reach the same fake.

`DockerEngineService` takes a `ClientFactory` and calls it where it called `docker.DockerClient`, with the same keyword arguments. `DockerEngineService.install(factory)` makes a service with that factory the process-wide one; `reset_instance` returns to the SDK.

Rejected: a hook that installs a built client. The SDK fails in its constructor when no engine answers (`GET /version`), so an installed client cannot stand for that engine, and the service's own wrapping of the failure (the endpoint's source, the Podman guidance for the default socket) would not run.

### The Protocols follow the SDK's own signatures

`devops_cli/docker/sdk.py` declares each call with the signature the SDK gives it. The SDK's models take `**kwargs` for `start`, `wait`, `logs`, `stats` and `remove`, so their Protocols do too: the SDK's low-level method, not the type checker, refuses a keyword. The fake refuses it the same way.

Rejected: an exact keyword list for `logs`. The SDK's `Container.logs` does not have one, so the Protocol would describe a stricter API than the SDK and hide that the SDK only fails at run time (#2520).

### The contract runs scenarios over the SDK, and one case over the service

Each scenario makes SDK calls on an `EngineClient` and returns what a caller sees, with IDs, times and byte counts left out. The suite runs it over the fake and over a real `docker.DockerClient` that reads recorded answers, and both must give the case's expected value. The unreachable engine is one case through the service on both sides, because the failure happens in the constructor, before any SDK call.

### The recorded answers are replayed on a Unix socket in the test's process

`RecordedEngine` serves one scenario's exchanges in order and answers a request outside the record with a 500, which the test sees in `unexpected`. It sends each reply in the framing the engine used: a length, chunks, or `101 UPGRADED` followed by raw frames after a 50 ms pause, so that the SDK's HTTP reader takes only the headers before the SDK reads the socket.

Rejected: `responses`, `requests-mock` and `vcrpy`, whose replies have no socket and no chunked raw stream (see the proposal's Feasibility). Rejected: a live engine (Q26 of #1307).

### The recording keeps only the scenarios' own objects

The engine of the recording host runs other work. The proxy sends every prune with a filter that matches nothing, so the recording deletes nothing; the record keeps the request as the SDK sent it and the engine's reply, which has the same form. The record keeps the objects named `devops-contract` and the engine's own networks, the facts of `/info` and `/version` that devops-cli reads, RFC 5737 and RFC 3849 addresses in place of private ones, and a build cache record's type in place of its description. Rejected: a record of the whole engine, which would hold other work's names and the host's addresses.

### The fixture is `docker_daemon`

`docker_daemon` installs a fake that holds `alpine:3` and points `DOCKER_HOST` at a socket path under the test's own directory, so the service resolves and checks the endpoint as it does a real one. The `docker_engine` factory stays for the tests of other packages (#1325, #1327, #1334, #1335); it installs a test's own client through `install` and leaves it unclosed for the test's assertions, and the floor resets the service after each test.
