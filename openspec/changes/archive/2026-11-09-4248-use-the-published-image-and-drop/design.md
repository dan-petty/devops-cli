# Design

## Decisions

- **Tag `latest`.** `devops devcontainer init` gives child repositories `CONST_DEVCONTAINER_PUBLISHED_IMAGE`, and the usage guide names `latest` for development environments. This repository uses the same image as its children. A rebuild uses the local copy of the tag, so the guide says to pull the tag first.
- **No `containerEnv` in the workspace.** Every entry except `UV_CACHE_DIR` is in the image label. Without the `.uv` volume, `UV_CACHE_DIR` has no purpose: the default `~/.cache/uv` is on the home volume, which all containers of the identity share.
- **Keep `remoteUser`.** The label also sets it, but the workspace file keeps the explicit value that the editor and `devops devcontainer validate` read.
- **Data mounts stay and are guarded.** The `.data` volume, the home volume (it also holds the keyring and its copies), the `.ssh` bind mount and the `/tmp` volume hold data that must outlive a container. A test fails if one of them leaves the configuration.

## Rejected alternatives

- **Pin a release tag or a digest.** It gives a reproducible container, but the project releases several times a day and has no Renovate configuration, so each bump would be a hand edit. A person who wants a pin can still set it.
- **Keep the local build for this repository only.** It keeps the two copies of the build definition and the slow rebuild. CI already builds and starts the image for every change to `.devcontainer` or `src`.
- **Also move `.data` to the workspace disk.** The volume holds agent worktrees and state. Moving it needs a copy step, and the owner asked that nothing in `.data` be lost, so it stays a volume.
- **Remove the volume guidance for child repositories.** Volumes still help a workspace on a Windows or macOS mount, so the scaffold and section 7 of the usage guide keep it.
