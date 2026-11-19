# Proposal

## Why

Issue #6336: the devcontainer does not have all the tools to manage an infra repo such as dan-petty/homelab. `ansible-lint` is not on PATH, `ansible` is ansible-core 2.21.4 from a `uv tool install` on the home volume while homelab pins 2.22.0, the collections are in `~/.ansible/collections` only because a person installed them, and the Kubernetes tools of the image follow the tools lock of devops-cli `main`, not the release that the homelab checks use. A copy of the pins of each infra repo in the image would give a second source for each version.

## What Changes

- Add the key `tools.install` to the project profile: the command, as a list of arguments, that installs the tools of the repository into its checkout. The type template `ansible-k8s` sets `["make", "install"]`, and `.devops/project.toml` can set another command or `[]`.
- `devops devcontainer post-start` runs `tools.install` in the checkout of each entry of `infra.repos`, with a bound of 600 s, and prints one line for each repo. A missing checkout, an invalid profile, a failed install or an install past its bound is a warning, and the start goes on.
- The dry run of post-start lists the install command of each infra repo and runs no command.
- Describe the key and the step in `CONTEXT.md`, `ARCHITECTURE.md` and `docs/DEVCONTAINER_USAGE.md`, and regenerate the command documents.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `infra-repo-tools`: Post-start installs the tools of each infra repo, A failed install is a warning, The dry run plans each install

### Modified Capabilities

- `project-profile`: The profile names the install command of the tools

## Impact

- Code: `src/devops_cli/project/profile.py`, `src/devops_cli/templates/profiles/ansible-k8s.toml`, `src/devops_cli/infra/tools.py`, `src/devops_cli/commands/devcontainer.py`, `src/devops_cli/devcontainer/devcontainer_plans.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `CONTEXT.md`, `ARCHITECTURE.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/CLI_REFERENCE.md`, `docs/commands/devcontainer.md`
- Tests: `tests/project/test_profile.py`, `tests/infra/test_tools.py`, `tests/commands/test_devcontainer.py`, `tests/infra/test_onboard.py`, `tests/commands/__snapshots__/test_infra_onboard.ambr`
- dan-petty/homelab needs `make install` (dan-petty/homelab#62) for the step to install its tools; before that, the step prints a warning for homelab.

## Feasibility

- In the devcontainer on 2026-11-18: `command -v ansible-lint` printed nothing; `ansible --version` printed `ansible [core 2.21.4]` from `~/.local/share/uv/tools/ansible/bin/ansible`; `helm version --short` printed `v4.3.2`, and the tools lock of the release v0.128.0 that the homelab checks use names helm 4.3.1.
- `config.yaml` has one entry in `infra.repos`, `dan-petty/homelab` with `path: null`, so its checkout is `<repos.base_dir>/dan-petty/homelab` (`default_checkout` at `src/devops_cli/infra/onboard.py:85`).
- A clean clone of the branch of dan-petty/homelab#62 ran `make install` in 102 s and a second `make install` in 1 s, with only uv, make, git and a shell on PATH; `make lint` and `make k8s-checks` then passed with the installed tools.
- `ProjectProfile` at `src/devops_cli/project/profile.py` forbids an unknown key (`extra="forbid"`), so the key must exist in devops-cli before a project file declares it; the type template gives it to homelab with no change of its project file.

## Existing Tool Considered

- The install itself uses the tools that the infra repo chose: for homelab, uv for its Python tools, ansible-galaxy for its collections and `devops install-tools` of the devops-cli release for its binaries. devops-cli only runs the command that the profile names.
- The devcontainer lifecycle hooks (`postStartCommand`) could run `make -C repos/dan-petty/homelab install` directly, but that names one repo and one path; the step reads `infra.repos`, so it works for each infra repo.
- Cost of the step: about 60 lines of code and 12 tests, 2 hours.
