# Design

## Decisions
- **`GitSettingsError` and `git_config` stay.** `_read_shallow` raises the error for a link, or anything but a regular file, at the `shallow` file of the clone. That handling stays until #3700, so the error, the class and the stop paths in `implement_run.py` stay for it. The tests of these stop paths now make the `shallow` file a link in place of a refused key.
- **One sweep before the folder.** `OriginGit` ran a sweep, the scan and a second sweep. With no scan, the two sweeps ran one after the other, so one goes. The sweep before the call with the token stays.
- **`_git` loses `isolated`.** Only the scan read the configuration of the clone, with `isolated=False`. Each other call ran isolated.

## Rejected alternatives
- **Keep the scan as a signal.** The audit of the git use of the roadmap Jobs and the owner decision on #6638 found that the scan protects no call with the token. It also starts a `core.fsmonitor` program before it refuses it, and it refuses Git LFS repositories, blobless clones and the `--shared` evaluation clone.
- **Delete `GitSettingsError` and `git_config` too.** `_read_shallow` still raises the error, and #6638 keeps the `shallow` file handling until #3700. A delete would leave a link at `shallow` with no class.
