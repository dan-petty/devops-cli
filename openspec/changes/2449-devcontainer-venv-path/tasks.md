# Tasks

## 1. The checkout's devops first on PATH

- [x] 1.1 Add the failing invariant test `tests/invariants/test_devcontainer_config.py`: the workspace configuration sets `remoteEnv.PATH` to `${containerWorkspaceFolder}/.venv/bin:${containerEnv:PATH}`, and the image configuration sets no `remoteEnv`
  - Verification: `uv run devops ci test tests/invariants/test_devcontainer_config.py` fails
- [x] 1.2 Set `remoteEnv.PATH` in `.devcontainer/devcontainer.json`
  - Verification: `uv run devops ci test tests/invariants/test_devcontainer_config.py tests/test_devcontainer.py`
- [x] 1.3 Tell in a comment in `.devcontainer/Dockerfile` why the image keeps its copy of devops, and in step 2 of the README quick start which `devops` the devcontainer runs
  - Verification: `uv run devops docs generate --sync-readme` leaves the command tables unchanged

## 2. Verification and static checks

- [ ] 2.1 Verify that the new test fails on the base tree
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] 2.2 Run the ratchets and the type check
  - Verification: `uv run devops ci test tests/test_swallowed_failures_ratchet.py tests/test_architectural_invariants.py` and `uv run mypy src`

## Workflow follow-up

- Pending a person: rebuild or reopen the devcontainer, open a new terminal, and check that `command -v devops` gives `<workspace>/.venv/bin/devops` and that `devops --version` equals `uv run devops --version`.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
