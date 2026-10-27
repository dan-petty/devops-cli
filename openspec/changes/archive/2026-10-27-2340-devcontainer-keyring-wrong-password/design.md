# Design

`_unlock_keyring` checks `_keyring_is_locked()` after running `gnome-keyring-daemon --replace --unlock`. When locked is True, it formats `ERRORS.devcontainer.keyring_wrong_password` with `path=_login_keyring_file()`.

The message states that the keyring is still locked, names the path of the keyring file, and gives the shell command to move the file to a backup and run `devops devcontainer unlock-keyring`.

## Rejected alternatives

- **Automated file deletion or overwrite without backup:** Overwriting or deleting the existing keyring automatically destroys existing credentials without confirmation. If the user remembers the password later, the secrets would be lost. Rejected.
- **Add a `--reset` option to `unlock-keyring`:** Moving the file explicitly with `mv` is transparent, standard, and requires no additional CLI flags or options. Rejected.
