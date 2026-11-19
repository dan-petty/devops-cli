## RENAMED Requirements

- FROM: `### Requirement: The build of the runner image fails on a missing tool or a wrong pin`
- TO: `### Requirement: The build of the runner image fails on a missing tool`

## MODIFIED Requirements

### Requirement: The runner stage holds the tools of a step
The `runner` stage of `Dockerfile` SHALL build from `runner-deps`, which builds from `deps`, installs the dev requirements of the `lock` stage, installs `git`, `curl` and `jq` with apt, and copies promtool from `runner-tools`, which installs it with `devops install-tools`. The image SHALL put the pinned OpenSpec, gh and Node on `PATH`, run as user 1000, and set `ENTRYPOINT ["devops"]`. `runner` SHALL come before `service`, which SHALL hold none of the added tools.

#### Scenario: The stage is read offline
- **WHEN** a test reads the stages of `Dockerfile`
- **THEN** the `runner` stage names `runner-deps` as its base, `runner-deps` names `deps` and installs `/lock/dev.txt` and `git`, and `runner` puts `/opt/devops-tools/bin` and `/app/.venv/bin` on `PATH`, sets `USER 1000:1000` and `ENTRYPOINT ["devops"]`, and stands before the `service` stage, which is the last stage of the file

#### Scenario: The base images stay pinned
- **WHEN** a test reads every `FROM` and `COPY --from` of `Dockerfile`
- **THEN** each image carries a digest, the `runner` stage included

#### Scenario: The added tools are the tools of the table
- **WHEN** a test reads the `runner-deps` stage
- **THEN** the apt packages of `runner-deps` are the apt tools of `RUNNER_TOOLS` and `ca-certificates`

### Requirement: The runner image holds each tool that the gate and the hooks need
`RUNNER_TOOLS` in `devops_cli.roadmap.runner_tools` SHALL list each program that the runner image must hold, its source, why it is there, and the command that proves it runs. `NOT_IN_RUNNER` SHALL name each program that the image leaves out, with the reason. The module SHALL hold no tool version: `Dockerfile` and `tools.lock` hold the pins.

#### Scenario: A source of the gate needs a program that is in neither table
- **WHEN** a program of a `devops ci` row, of a hook of `.pre-commit-config.yaml`, of a required job of `ci.yml` or of a live-marked test is in neither `RUNNER_TOOLS` nor `NOT_IN_RUNNER`
- **THEN** a test fails and names the program

#### Scenario: A pin drifts from the Dockerfile
- **WHEN** a pull request changes the version of uv, gh, Node, Python or actionlint in `Dockerfile`
- **THEN** it changes no file under `src/`, because `RUNNER_TOOLS` holds no version and no test compares a version with `Dockerfile`

### Requirement: The build of the runner image fails on a missing tool
The last step of the `runner` stage SHALL run `python -m devops_cli.roadmap.runner_tools` as user 1000. The check SHALL fail when a program is not on PATH or its version command exits non-zero. For a dev dependency and for the project, it SHALL also fail when the output lacks the version of the installed distribution. It SHALL compare no other version.

#### Scenario: A tool is missing or at another version
- **WHEN** a program of the table is not on PATH, its version command exits non-zero, or a dev dependency prints a version other than the version of its installed distribution
- **THEN** the check names the tool and exits 1

#### Scenario: A tool that the image pins prints any version
- **WHEN** the version command of a tool that `Dockerfile` or `tools.lock` pins exits 0
- **THEN** the check of the tool passes, and the check runs only that version command

#### Scenario: Every tool passes
- **WHEN** every version command exits 0, and each dev dependency prints its installed version
- **THEN** the check prints the number of tools and exits 0
