# Design

## Decisions

- **No display for the bus and the daemon.** gcr-prompter is D-Bus activated and inherits the environment of `dbus-daemon`. `_start_session_bus` and `_unlock_keyring` stop naming `DISPLAY` and `WAYLAND_DISPLAY` in `extra_allowed_env`, so `build_subprocess_env` drops them. Without a display, gcr-prompter cannot open, and gnome-keyring never calls `fix_login_keyring_if_unlock_failed`. A wrong password at `unlock-keyring` then has no lasting effect.
- **No post-start prompt.** The VS Code lifecycle terminal doubles each key, so no password typed there can be correct. The shell hook that post-create writes already asks in the first interactive terminal while the pending marker exists. post-start keeps the marker and only prints the bus action, which names `devops devcontainer unlock-keyring`.
- **Copy after each successful unlock.** At that moment the daemon has just opened the file with the typed password, so the copy opens with the same password. The copy goes to `<keyrings>/backups/login.keyring.<UTC YYYYMMDD-HHMMSS>`, mode 0600, in a folder with mode 0700. The command skips the copy when the file is equal to the newest copy, so the kept copies are different versions. It deletes the oldest copies past `CONST_KEYRING_BACKUP_COUNT`. Only names that start with `login.keyring.` in that folder are counted, so a manual backup next to the keyring is never deleted.
- **A failed copy does not fail the unlock.** The keyring is open and usable, so the command prints a warning with the error and exits 0.
- **The wrong-password error names the copies.** The user can copy one over `login.keyring` and run `unlock-keyring` again.

## Rejected alternatives

- **Copy at each credential change.** It needs `inotifywait` or a D-Bus signal listener that runs all the time, started and kept alive by post-start. With the display removed, the known cause cannot occur, and a copy per unlock loses at most the changes of one session.
- **Strip the doubled characters at post-start.** That would guess at the lifecycle terminal's fault and could corrupt a real password with a repeated character.
- **Unlock with `UnlockWithMasterPassword` over D-Bus in place of `--unlock`.** It does not mark a failed login unlock, but `--replace` is also what gives the daemon its own session (see `setsid`). With no GUI prompt, the mark has no effect, so the simpler change is enough.
- **Mask gcr-prompter with user D-Bus service files.** That is a change to the home volume, outside the image and the code, and the environment already decides the display.
- **Copy in the keyring folder itself.** gnome-keyring loads only `*.keyring` there, but a pruned file next to manual backups (`login.keyring.bak-<stamp>`) could delete one of them. A separate folder keeps the pruning to its own copies.
