# Tasks

## 1. No display for the keyring (behavior)

- [x] 1.1 Write failing tests: the environment that `build_subprocess_env` builds for `dbus-daemon` and for `gnome-keyring-daemon` holds neither `DISPLAY` nor `WAYLAND_DISPLAY` when the container sets them.
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`
- [x] 1.2 Remove `DISPLAY` and `WAYLAND_DISPLAY` from `extra_allowed_env` in `_start_session_bus` and `_unlock_keyring`.
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`

## 2. No post-start prompt (behavior)

- [x] 2.1 Write a failing test: post-start with a terminal on standard input and the pending marker starts no unlock and keeps the marker. Delete the tests of the post-start prompt and of the prompt timeout.
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`
- [x] 2.2 Remove the post-start prompt, `_stdin_is_terminal`, the timeout of `_read_password` and `_unlock_keyring`, and `CONST_KEYRING_PROMPT_TIMEOUT_SECONDS`.
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`

## 3. A copy after each successful unlock (behavior)

- [x] 3.1 Write failing tests: the first copy with its modes and output line, no copy of an unchanged keyring, the oldest copy goes past `CONST_KEYRING_BACKUP_COUNT`, no copy after a wrong password, and the wrong-password error names the backup folder.
  - Verification: `$ uv run devops ci test tests/commands/test_devcontainer.py`
- [x] 3.2 Add `CONST_KEYRING_BACKUP_COUNT`, copy the keyring after a successful unlock, and name the backup folder in `ERRORS.devcontainer.keyring_wrong_password`. Regenerate the documentation.
  - Verification: `$ uv run devops docs generate --sync-readme`

## 4. Documents

- [x] 4.1 Update the keyring section of `docs/DEVCONTAINER_USAGE.md`: the first terminal asks, no GUI prompt and why, and the copies with how to go back to one.
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
