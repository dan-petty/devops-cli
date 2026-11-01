## MODIFIED Requirements

### Requirement: The runner stage holds the tools of a step
The `runner` stage of `Dockerfile` SHALL be built from the `builder` stage and SHALL run `uv sync --locked`, so that the dev dependencies of `uv.lock` are in the venv. It SHALL install `git`, `shellcheck`, `curl` and `jq` with apt, SHALL copy actionlint from the image that `.devcontainer/Dockerfile` names by the same digest, and SHALL install Trivy and promtool with `devops install-tools`. It SHALL put the pinned OpenSpec, gh and the Node runtime of the builder stage on the stage's `PATH`, SHALL run as user 1000, and SHALL set `ENTRYPOINT ["devops"]`. It SHALL come before the `service` stage, so that a build with no `--target` builds the Service image. The `service` stage SHALL hold none of the added tools.

#### Scenario: The stage is read offline
- **WHEN** a test reads the stages of `Dockerfile`
- **THEN** the `runner` stage names `builder` as its base, runs `uv sync --locked` with no `--no-dev`, installs `git`, puts `/opt/devops-tools/bin` and `/app/.venv/bin` on `PATH`, sets `USER 1000:1000` and `ENTRYPOINT ["devops"]`, and stands before the `service` stage, which is the last stage of the file

#### Scenario: The base images stay pinned
- **WHEN** a test reads every `FROM` and `COPY --from` of `Dockerfile`
- **THEN** each image carries a digest, the `runner` stage included

#### Scenario: The added tools are the tools of the table
- **WHEN** a test reads the `runner` stage
- **THEN** its apt packages are the apt tools of `RUNNER_TOOLS` and `ca-certificates`, it runs `devops install-tools --tool <name>` for each tool of the lock in the table except OpenSpec, and the `service` stage runs no `devops install-tools`

## ADDED Requirements

### Requirement: The runner image holds each tool that the gate and the hooks need
`RUNNER_TOOLS` in `devops_cli.roadmap.runner_tools` SHALL list each program that the runner image must hold, its source, why it is there, and the command that proves it runs. `NOT_IN_RUNNER` SHALL name each program that the image leaves out, with the reason.

#### Scenario: A source of the gate needs a program that is in neither table
- **WHEN** a program of a `devops ci` row, of a hook of `.pre-commit-config.yaml`, of a required job of `ci.yml`, of a live-marked test, or of `tools.lock` is in neither `RUNNER_TOOLS` nor `NOT_IN_RUNNER`
- **THEN** a test fails and names the program

#### Scenario: A pin drifts from the Dockerfile
- **WHEN** the version of uv, gh, Node, Python or actionlint in the table differs from the Dockerfile, or the actionlint image of the two Dockerfiles differs
- **THEN** a test fails

### Requirement: The build of the runner image fails on a missing tool or a wrong pin
The last step of the `runner` stage SHALL run `python -m devops_cli.roadmap.runner_tools` as user 1000. The check SHALL fail when a version command exits non-zero, when its output lacks the pin, or when a tool of the lock is not linked at its locked version. The pin SHALL come from `uv.lock`, `tools.lock` or the Dockerfile, by the source of the tool.

#### Scenario: A tool is missing or at another version
- **WHEN** a version command exits non-zero, prints no pin, or a tool of the lock is not linked at its locked version
- **THEN** the check names the tool and exits 1

#### Scenario: Every tool passes
- **WHEN** every version command prints its pin
- **THEN** the check prints the number of tools and exits 0

### Requirement: The smoke test of the runner image uses the table and bounds the image size
The smoke test of the runner image in `ci.yml` and in `release.yml` SHALL be the same text, SHALL run `python -m devops_cli.roadmap.runner_tools` on the loaded image, and SHALL fail when the image is larger than 3000000000 bytes. It SHALL hold no version command of its own for a tool of the table.

#### Scenario: The smoke test is read offline
- **WHEN** a test reads the smoke test of both workflows
- **THEN** the two texts are equal, they run the check module and the size bound, and no line runs `--entrypoint <tool> "$IMAGE" --version`
