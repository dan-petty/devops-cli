# Tasks

## 1. Registry module and contract tests (kind: behavior)

- [x] 1.1 Write failing tests in `tests/core/test_passthrough.py` for `REGISTRY['gh run list']`, `NEVER_WRAPPED`, `devops_paths` resolution, operational limits, and MCP allowlist invariants
  - Verification: `$ uv run devops ci test tests/core/test_passthrough.py`
- [x] 1.2 Implement `src/devops_cli/core/passthrough.py` with `PassthroughEntry`, `NEVER_WRAPPED`, and `REGISTRY['gh run list']`
  - Verification: `$ uv run devops ci test tests/core/test_passthrough.py`

## 2. Architecture Decision Record and index (kind: documents)

- [x] 2.1 Add `docs/adr/0037-tool-commands-mirror-and-pass-through-options.md`, set `status: accepted` with `body-hash`, and regenerate `docs/adr/README.md` via `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`

## 3. Verification gate

- [x] 3.1 Pass `uv run devops docs check` and full local CI gate `uv run devops ci --check`
  - Verification: `$ uv run devops ci --check`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
