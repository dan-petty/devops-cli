# Tasks

## 1. Specification Tests

- [x] 1.1 Add failing specification tests in `tests/test_devcontainer.py` asserting that failed downloads for `uv` and `claude` report failure warnings and not success messages, and successful downloads report installation messages. Verify failure on unpatched code with `uv run devops ci test tests/test_devcontainer.py`.

## 2. Implementation

- [x] 2.1 Update installer commands in `_bootstrap_developer_tools` in `src/devops_cli/commands/devcontainer.py` to execute with `bash -o pipefail -c`.
- [x] 2.2 Verify tests pass with `uv run devops ci test tests/test_devcontainer.py`.

## 3. Verification and OpenSpec Archive

- [x] 3.1 Run `uv run devops ci fail-to-pass --base origin/main` to verify the failing test evidence against the base tree.
- [x] 3.2 Run `uv run devops ci` to ensure all quality gates pass.
- [x] 3.3 Archive the OpenSpec change with `uv run devops openspec archive 1728-devcontainer-installer-download-failure`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
