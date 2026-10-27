# Proposal

## Why

Issue #2340: After a devcontainer rebuild from a new image, `devops devcontainer unlock-keyring` rejects the keyring password when the entered password differs from the password used to create the persisted keyring file. The current error message ("Wrong password; the keyring is still locked.") provides no remedy or way forward.

## What Changes

- When an existing keyring rejects the password, `devops devcontainer unlock-keyring` prints an error message that names the keyring file path and provides the exact procedure to back up the file and reset the keyring.
- The error message text in `src/devops_cli/lang/en/errors.py` is updated to include the file path and reset instructions.
- A test in `tests/test_devcontainer.py` verifies that the error output contains the path and reset command.

## Capabilities

### New Capabilities

- `devcontainer-keyring-unlock`: requirements for reporting keyring unlock failure with actionable remediation steps.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/lang/en/errors.py`, `tests/test_devcontainer.py`.

## Feasibility

- Upstream `gnome-keyring` source code (`pkcs11/secret-store/gkm-secret-binary.c`, `egg/egg-symkey.c`) confirms that the binary keyring format (`GnomeKeyring\n\r\0\n`, AES-128-CBC, SHA-256 key derivation with salt and iterations, MD5 integrity check) has remained unchanged across versions (42 through 51.1).
- The rejection occurs because the user's home volume persists `~/.local/share/keyrings/login.keyring` across image rebuilds, and the password entered does not match the master password used to encrypt the file.
- Because AES-128 encryption protects the keyring, recovering data without the original password is not possible.
- Naming the path and the reset command (`mv <path> <path>.bak` and `devops devcontainer unlock-keyring`) gives the user a clear way forward.

## Existing Tool Considered

No outside tool applies. The change updates an error message string and formats it with the existing keyring file path in the `unlock-keyring` command.
