# Tasks

- [x] 1.1 Write failing test in `tests/test_devcontainer.py` asserting that a wrong password on an existing keyring prints the file path and reset instructions.
- [x] 1.2 Update `ERRORS.devcontainer.keyring_wrong_password` in `src/devops_cli/lang/en/errors.py` with the path placeholder and remediation instructions in ASD-STE100.
- [x] 1.3 Update `_unlock_keyring` in `src/devops_cli/commands/devcontainer.py` to format `ERRORS.devcontainer.keyring_wrong_password` with `_login_keyring_file()`.
- [x] 1.4 Run `devops ci fail-to-pass --base origin/main` to verify the check passes.
- [x] 1.5 Run `devops openspec check` and full checks `devops ci`.
