# Tasks

## 1. Kilo Code configuration

- [ ] Add the failing tests in `tests/test_devcontainer.py`
  - Verification: `uv run devops ci test tests/test_devcontainer.py`
- [ ] Add `kilo_mcp.json.j2`, the scaffold and sync code, and `kilo.jsonc`
  - Verification: `uv run devops ci test tests/test_devcontainer.py`
- [ ] Update `docs/DEVCONTAINER_USAGE.md` and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
