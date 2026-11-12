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
- **WHEN** a test reads the `runner-deps` and `runner-tools` stages
- **THEN** the apt packages of `runner-deps` are the apt tools of `RUNNER_TOOLS` and `ca-certificates`, `runner-tools` runs `devops install-tools --tool <name>` for each tool of the lock in the table except OpenSpec, and neither `service` nor `service-deps` runs `devops install-tools`

### Requirement: The runner stage deletes what only the build needs
The runner image SHALL hold no npm, no pip and no uv cache of root, because a Job installs no tool and the scan of the image fails on the findings in them. `runner-deps` SHALL delete pip, no stage under `runner` SHALL copy npm, and each uv install SHALL keep its cache in a cache mount.

#### Scenario: The stage is read offline
- **WHEN** a test reads the `runner`, `runner-deps` and `deps` stages
- **THEN** none of them names `node_modules/npm`, a `RUN` of `runner-deps` deletes the pip files of site-packages, and every `uv pip` of them mounts `type=cache,target=/root/.cache/uv`
