# Design

## Decisions

- **The install command is a key of the project profile, `tools.install`, and the type template `ansible-k8s` sets `["make", "install"]`.**: The profile holds the facts of a repository and the config of devops-cli holds operational keys only (`InfraRepoConfig`), so the command belongs to the repository. The template gives the command to homelab with no change of its `.devops/project.toml`, which an older devops-cli would refuse (`extra="forbid"`).
- **The command is a list of arguments, not a shell line.**: `run_subprocess` runs with `shell=False`, and a list needs no quoting rules.
- **Post-start runs the install, not post-create.**: The clones under `repos/` are on the workspace bind mount and can come after the container is created. A start after a clone or a `git pull` that changes a pin installs the new versions. The install of homelab is idempotent and takes about 1 s when nothing changed.
- **The install runs in the foreground of post-start, with a bound of 600 s (`DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS`).**: VS Code opens the window before post-start ends (`waitFor` is `updateContentCommand` by default), and one line for each repo shows the result. The first install of homelab took 102 s.
- **The install reads the working tree of the checkout, not the default branch at origin.**: It installs the tools that the checkout uses. `devops infra plan` and `apply` keep reading the default branch at origin for host changes.
- **Each failure is a warning line, and the next repo goes on.**: A start must not fail for an infra repo, as the pre-commit step of post-start does.

## Rejected alternatives

- **Copy the pins of homelab into the Dockerfile or `tools.lock` of devops-cli.**: homelab pins ansible-core, ansible-lint and shellcheck in its own lock and takes its binaries from the tools lock of the release in `k8s/devops-cli-copy.json`; a copy in devops-cli is a second source that drifts at each bump.
- **A setting in `infra.repos` for the command.**: `InfraRepoConfig` holds operational keys only, and the docstring of the class says that the facts of a repository are in its project profile.
- **A new command `devops infra install-tools`.**: `make install` in the checkout already does it for a person; the gap is the devcontainer start, and `devops devcontainer post-start` can be run again by hand.
- **Run `make install` only when the Makefile has an `install` target.**: The profile already names facts by type; a Makefile parse is a second rule for one fact.

## Security

The step runs a command that a file of the infra repo names (`tools.install` of `.devops/project.toml`, else the type template) in its checkout, with the isolated child environment of `run_subprocess`. Only a person writes `infra.repos` in `config.yaml`, so only the checkouts of repos that a person listed run. The command runs the code of the checkout, as `make install` by a person does. A person must confirm that the step reads `infra.repos` only and runs no command for another folder; `test_the_install_command_of_the_template_runs_in_each_checkout` in `tests/infra/test_tools.py` asserts the folder of each call.
