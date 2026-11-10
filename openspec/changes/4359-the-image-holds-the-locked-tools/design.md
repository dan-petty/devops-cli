# Design

## Decisions

- Each tool comes from the native step of its kind. A binary downloads in the `tools` builder stage with `curl` and `sha256sum -c`, and the stage keeps only the commands in `/out/bin`, so `curl` and `unzip` are not in the image. A Python tool installs with `uv pip sync --require-hashes` into a virtual environment of its own. A Node tool installs with `npm ci --ignore-scripts` in a pinned Node stage, and only the installed folder is copied.
- The Filesystem Hierarchy Standard names `/usr/local` for software that the administrator installs: the commands are in `/usr/local/bin`, which is on `PATH`, and the files of a Python or Node tool are in `/usr/local/share/devops-tools`.
- The tool steps come before the copy of `src/` and read only the lock files they need, so a source change rebuilds none of them.
- Post-create installs no locked tool, so no file of a tool lands in the home volume.
- The url and sha256 of each binary are in the Dockerfile. The Python requirements files and the Node lockfiles stay in `src/devops_cli/tools_lock/` until the removal of `tools.lock` moves them. A test fails when the Dockerfile and `tools.lock` differ.

## Rejected alternatives

- Keep the install in post-create and add `~/.local/bin` to `PATH`. Rejected: the installed files stay in the home volume between rebuilds, and a tool is not part of the image. The first attempt at this passed its test and still left the files outside the image.
- Install into `/opt/devops-tools`. Rejected: `/usr/local` is the standard root for administrator-installed software, and the user asked for it.
- Add cache mounts for `npm` and `uv`. Rejected: `install_tools.py` gives `npm` an empty cache of its own on purpose, so that the sha512 and malware checks decide what installs.
- Run `devops install-tools` in the image build. Rejected: the user asked for the native steps of Docker, and the command is a custom installer in the source of this package that three follow-up items remove.
- Cache mounts for `npm` and `uv`. Rejected for `npm`: the build installs from a lockfile that npm checks, and the Node stage keeps no cache. Accepted for `uv`, as the other `uv` steps of the file use one.
