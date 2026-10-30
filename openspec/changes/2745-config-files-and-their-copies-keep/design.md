# Design

## Decisions

- **Use os.chmod on the tmp file before os.replace**: The tmp file has the correct mode before it becomes the live file. No window of wrong mode is visible to other users.
- **Use 0600 as the default mode for a new config file**: Owner read/write only. A config file can hold secrets, so no other user should read it.
- **Keep shutil.copystat in _copy after the os.chmod**: copystat also copies timestamps. The os.chmod closes the mode window; copystat preserves the rest of the metadata.

## Rejected alternatives

- **Call shutil.copystat after os.replace**: The live file briefly has the umask mode between os.replace and copystat. A window of wrong mode is visible to other users.
- **Use 0644 (umask default) for new files**: World-readable. Insecure for files that can hold secrets. This is the current buggy behavior that #2745 reports.
