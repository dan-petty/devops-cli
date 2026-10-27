# Tasks

## 1. Kilo Code configuration

- [x] Add the failing tests in `tests/test_devcontainer.py`
  - Verification: `uv run devops ci test tests/test_devcontainer.py`
- [x] Add `kilo_mcp.json.j2`, the scaffold and sync code, and `kilo.jsonc`
  - Verification: `uv run devops ci test tests/test_devcontainer.py`
- [x] Update `docs/DEVCONTAINER_USAGE.md` and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
