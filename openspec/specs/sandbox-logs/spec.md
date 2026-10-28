# sandbox-logs Specification

## Purpose
How `devops sandbox logs` reads the log of a sandbox container from the engine: each line with the stream it was written to, in the order the engine stored, with the tail, timestamps and follow options.

## Requirements

### Requirement: A sandbox log keeps the stream of each line
`DockerEngineService.container_log_stream` SHALL read the container's log through a call that the locked docker SDK has, and SHALL give each frame as `(stdout, stderr)` bytes, with the bytes of one stream in each frame, in the order of the engine's reply. It SHALL keep the `tail`, `timestamps` and `follow` options.

#### Scenario: A container writes to both streams
- **WHEN** a container that wrote `hello` to stdout and `oops` to stderr has its log read
- **THEN** the frames give `hello` on stdout and `oops` on stderr, over the Docker engine fake and over the docker SDK client reading answers recorded from Docker Engine 29.9.2

#### Scenario: Tail, timestamps and follow
- **WHEN** the same log is read with `tail=1`, with `timestamps=True` and with `follow=True` after the container stopped
- **THEN** the tail gives one line, each timestamped line starts with an RFC 3339 time and keeps its stream, and the followed read ends with both lines

#### Scenario: A container with a TTY
- **WHEN** a container that runs with a TTY writes to both streams and has its log read
- **THEN** every line comes on stdout, as the engine joins the two streams in the TTY

### Requirement: A refused log read names the failure
When the engine refuses the log request or cannot be reached, `container_log_stream` SHALL raise `DockerEngineError` with the text `Container log stream failed`.

#### Scenario: The engine fails the request
- **WHEN** the engine fails the log request of a sandbox container
- **THEN** `devops sandbox logs` stops with `DockerEngineError` and the text `Container log stream failed`
