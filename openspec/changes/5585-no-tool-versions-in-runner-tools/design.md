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
- **Remove the pins and also let `is_source_code` parse a module, so that a pin-only module is no source code.** The design that the refine job added to #5585 asks for this guard, after the owner comment of 2026-11-19T03:54. The `## Fix` section that the owner wrote later on 2026-11-19 does not have it. The guard would match no module, so it would be compensating code (AGENTS.md rule 2):
  - The guard keeps a module with a function or a class as source code. `runner_tools.py` on `origin/main` holds classes and functions next to its four pins, so the guard would not have changed the result of #6370.
  - After this change, no module under `src/` holds only a tool version. An AST scan of `src/` finds one module that holds only assignments and a version name: `src/devops_cli/config/defaults.py`, with 642 assignments. Its `DEFAULT_PYTHON_VERSION` stays until order 7 of the issue removes it.
  - The owner rule of 2026-11-19 forbids a tool version in a `.py` file. A guard that lets a pin-only module skip the check would make such a file easier to add.
  - `stage_change.py` calls `is_source_code` with the planned paths of a change, which can be files that do not exist yet. A parse needs the file.
  So `is_source_code` stays a rule of the path, and the header of `fail-to-pass.yml` agrees with it, because no pin stays in a `.py` file.
