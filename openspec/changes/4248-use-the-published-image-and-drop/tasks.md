# Tasks

## 1. The workspace devcontainer uses the published image (behavior)

- [x] 1.1 Write failing invariant tests: the workspace configuration names `CONST_DEVCONTAINER_PUBLISHED_IMAGE`, has no `build`, no `features` and no `containerEnv` key of the image configuration, and the workspace lock file does not exist; it mounts no cache volume and sets no `UV_CACHE_DIR`; it keeps the four data mounts.
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py`
- [x] 1.2 Change `.devcontainer/devcontainer.json` to the published image, remove `features`, `containerEnv` and the five cache mounts, and delete `.devcontainer/devcontainer-lock.json`. Delete the test that compared the two copies of the build, and read the Node pin from the image configuration and its lock only. Change the `.venv` comment of the Dockerfile.
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py tests/commands/test_devcontainer.py`

## 2. The inventory reads the lock of each configuration folder (behavior)

- [x] 2.1 Write a failing test: a repository with only `.devcontainer/image/devcontainer-lock.json` gives one devcontainer feature component with that file and line.
  - Verification: `$ uv run devops ci test tests/research/test_inventory.py`
- [x] 2.2 Read every file that matches `.devcontainer/devcontainer-lock.json` or `.devcontainer/*/devcontainer-lock.json`, and name each file from the repository root.
  - Verification: `$ uv run devops ci test tests/research/`

## 3. Documents

- [x] 3.1 Update `docs/DEVCONTAINER_USAGE.md` (the image build definition, this repository's devcontainer, a new release, an image change before a release, removal of the old cache volumes by name) and the shell note of `CONTRIBUTING.md`.
  - Verification: `$ uv run devops ci docs`

- Pending a person: before the rebuild, export the `devops-cli-data` and `global-devcontainer-home` volumes and copy `~/.ssh` on the host, as `docs/DEVCONTAINER_USAGE.md` says.
- Pending a person: rebuild the container (`Dev Containers: Rebuild Container`), run `uv sync --all-groups --all-extras`, and remove the five old cache volumes by name.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
