# Proposal: #4240

## Why

Closes #4240. After a container start, the devcontainer keyring rejects the correct password, and every credential in it becomes unavailable. This occurred three times.

The cause has two parts:

1. `devops devcontainer post-start` asks for the keyring password on the VS Code lifecycle terminal. That terminal sends each key two times. post-start gives the doubled password to `gnome-keyring-daemon --replace --unlock`, and the daemon rejects it.
2. gnome-keyring keeps the last password that `--unlock` rejected. The bus and the daemon get `DISPLAY` and `WAYLAND_DISPLAY`, so a client request opens the GUI prompt "Unlock Login Keyring" (gcr-prompter). When the user types the correct password there, gnome-keyring changes the master password to the rejected one and saves the file. It shows no message.

## What Changes

- `devops devcontainer post-start` starts the D-Bus session bus without `DISPLAY` and `WAYLAND_DISPLAY`, and `devops devcontainer unlock-keyring` starts `gnome-keyring-daemon` without them. No GUI prompt can open, so gnome-keyring cannot change the password to a rejected one. A client that asks for a secret while the keyring is locked gets a dismissed prompt at once.
- `devops devcontainer post-start` does not ask for the keyring password. The first interactive terminal asks for it (the existing shell hook). The password timeout and its constant are removed.
- After each successful unlock, `devops devcontainer unlock-keyring` copies `login.keyring` to the folder `backups` next to it, when the file differs from the newest copy. It keeps the newest `CONST_KEYRING_BACKUP_COUNT` (10) copies and prints the path of a new copy.
- The wrong-password error names the backup folder and tells how to go back to a copy.

This changes command behavior and a message, so the change carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `devcontainer-keyring-unlock`: the daemon and the bus get no display, post-start does not ask for the password, a successful unlock keeps a copy of the keyring file, and the wrong-password error names the copies.

## Impact

- `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_devcontainer.py`, `docs/DEVCONTAINER_USAGE.md`.
- Users unlock in a normal terminal. The GUI prompt does not open in the devcontainer.
- The change fits one pull request.

## Feasibility

- gnome-keyring 51.1 source, the version in the image (`dpkg -l gnome-keyring`: 51.1-3):
  - `daemon/login/gkd-login.c` `unlock_or_create_login` calls `gkm_wrap_layer_mark_login_unlock_failure (master)` when `--unlock` gets a wrong password.
  - `pkcs11/wrap-layer/gkm-wrap-prompt.c` `fix_login_keyring_if_unlock_failed` runs only after a successful unlock through the GUI prompt, and sets that kept password as the new master password.
  - `daemon/gkd-main.c` `read_login_password`: "All data (including newlines) are part of the password."
  - `egg/egg-file-tracker.c` and `pkcs11/secret-store/gkm-secret-module.c` load only `*.keyring` files at the top of the keyring folder, so a `backups` subfolder never loads as a collection.
- An offline check of the two lost keyring files tried 5,355 changes of the correct password. Only "every character doubled" opened them.
- A sandbox (own bus, runtime folder and data folder, no display) showed:
  - The post-start lock read-back is correct: a correct password reads back unlocked at once, and a wrong one reads back locked. So the post-start "Wrong password" is real.
  - A client unlock request on a bus with no display returns "dismissed" after 0.0 s, and the collection stays locked. No client hangs.
- `build_subprocess_env` keeps `DISPLAY` and `WAYLAND_DISPLAY` only when the caller names them in `extra_allowed_env`. Without them, the child environment holds neither.

## Existing Tool Considered

- gnome-keyring has no backup or snapshot feature. Seahorse can export a keyring only through its GUI.
- `savelog` (debianutils, in the image) rotates a file by moving it, which is for logs that a writer reopens. The daemon owns `login.keyring`, so the change must copy it first, and `savelog` would only add numbered names and a subprocess. The change uses `shutil.copy2` and `pathlib` from the standard library: about 20 lines, about 5,000 tokens to build, and little upkeep.
- A copy at each credential change needs a file watcher (`inotifywait` from inotify-tools) that runs all the time. A copy after each successful unlock needs no process, and the password is known to open that copy.
- The change deletes `_stdin_is_terminal`, the timeout and `SIGALRM` handling of `_read_password`, `CONST_KEYRING_PROMPT_TIMEOUT_SECONDS`, the post-start prompt and its three tests.
