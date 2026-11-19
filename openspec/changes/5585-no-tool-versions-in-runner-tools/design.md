# Design

## Decisions

- **The check is a presence check.** Each tool of `RUNNER_TOOLS` must be on PATH, and its version command must exit 0. `Dockerfile` and `tools.lock` hold the pins, and the build installs what they name, so a second copy of a version in the module only adds a file for each bump to change.
- **A dev dependency and the project keep their version compare.** `expected_text` reads the version of the installed distribution with `importlib.metadata`. That version is in the image itself, not a copy in a file, and the compare shows that the program on PATH is the one of the venv.
- **A tool of the lock gets no `devops install-tools --check`.** That call compared the link in `/opt/devops-tools/bin` with `tools.lock`, which is a pin compare. The stage `runner-tools` installs each tool from `tools.lock`, and the version command proves that the link runs.
- **The sources `IMAGE_PIN` and `TOOLS_LOCK` stay.** They tell where the image gets a tool, which a person and the stage context read.
- **The smoke step keeps `DEVOPS_CLI_USER_DATA_ROOT`.** The check no longer reads the variable, but `devops --version` runs with it as before. A change of the step and of the two workflow smoke tests is outside this item.
- **The `uv` and `node` groups keep `fix(deps):`.** Their members of `Dockerfile` are base images of the service image, and that rule gives them the prefix. Only the description changes.

## Rejected alternatives

- **Keep the pins and change the `Fail-to-Pass Check`.** The comments of #5585 show that `release_title` counts any file under `src/devops_cli/` as runtime code. A check that skips a pin in a `.py` file would be an escape, and the owner rule of 2026-11-19 removes the copies instead.
- **Keep the pins without a test.** A pin that no test compares with the Dockerfile drifts, and the build then fails on a version that the Dockerfile does not name. The owner rule forbids the copy.
- **Read the versions from `Dockerfile` at run time.** The image does not hold its `Dockerfile`, and the parse would add code for a value that the build already sets.
