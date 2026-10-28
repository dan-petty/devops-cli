# Tasks

## 1. A sandbox log keeps the stream of each line

- [x] Add failing tests: a contract scenario that reads a container's log as frames with `tail`, `timestamps`, `follow` and a TTY, over the Docker engine fake and over the answers recorded from Docker Engine 29.9.2; and the sandbox engine's log tests over the fake, with each line's stream
  - Verification: `uv run devops ci test tests/docker/test_engine_contract.py tests/test_sandbox_logs.py`
- [x] Record the new scenario from a local engine, and keep the other scenarios' recordings
  - Verification: `uv run devops ci test tests/docker/test_engine_contract.py`
- [x] Read the log through the SDK client's session and the SDK's `demux_adaptor` in `container_log_frames`, call it from `container_log_stream`, name the session's parts in `EngineApi`, and serve the request in the fake from a container's scripted frames
  - Verification: `uv run devops ci test tests/docker/ tests/test_sandbox_logs.py tests/test_docker_engine.py`
- [x] Delete the `demux=True` call of `container.logs` and the mock clients of the sandbox log tests, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2520-sandbox-logs-streams`
- Pending a person: run `devops sandbox logs <sandbox>` on a running sandbox and see its stdout and stderr lines.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
