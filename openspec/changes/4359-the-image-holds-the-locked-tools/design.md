# Design

## Decisions

- The image build installs every locked tool with `devops install-tools --target-dir /usr/local/bin` and `DEVOPS_CLI_USER_DATA_ROOT=/usr/local/share/devops-cli` for that one step. The Filesystem Hierarchy Standard names `/usr/local` for software that the administrator installs, and `/usr/local/bin` is on `PATH` already, so the image sets no `PATH`.
- The Node runtime that `npm ci` needs is mounted from the pinned Node image for that one step and is not copied into the image. The shebang of `openspec` finds the Node of the Node feature at run time.
- Post-create installs no locked tool, so no file of a tool lands in the home volume.

## Rejected alternatives

- Keep the install in post-create and add `~/.local/bin` to `PATH`. Rejected: the installed files stay in the home volume between rebuilds, and a tool is not part of the image. The first attempt at this passed its test and still left the files outside the image.
- Install into `/opt/devops-tools`. Rejected: `/usr/local` is the standard root for administrator-installed software, and the user asked for it.
- Add cache mounts for `npm` and `uv`. Rejected: `install_tools.py` gives `npm` an empty cache of its own on purpose, so that the sha512 and malware checks decide what installs.
