## MODIFIED Requirements

### Requirement: The runner stage names its interpreter
The `runner` stage SHALL set `UV_PYTHON` to the Python of the devtools image and `UV_PYTHON_DOWNLOADS` to `never`, and the shell of a step SHALL get `UV_PYTHON`. The `.python-version` of a checkout can name a patch release that the devtools image lacks, so `uv run` would find no interpreter.

#### Scenario: uv finds an interpreter
- **WHEN** CI runs `uv run --locked ruff --version` in a copy of the checkout, in the runner image with a read-only root, a tmpfs home, no capability and no new privileges
- **THEN** the command prints the ruff version of `uv.lock` and exits 0

### Requirement: The local hooks run only programs that the runner image holds
Each `language: system` hook of `.pre-commit-config.yaml` SHALL start with `uv run`, and the tool that it runs SHALL be a dev dependency of the lock (`ast-grep-cli`, `devops`) or a program of `RUNNER_TOOLS` (`openspec`). The `pre-commit` package SHALL be a dev dependency of the lock. The hook environments SHALL be fetched at run time into the home volume, because the perimeter admits public HTTPS.

#### Scenario: A hook that needs another program
- **WHEN** a local hook has the entry `vale`
- **THEN** the test fails and names the hook and the program

#### Scenario: The config as it is
- **WHEN** the test reads `.pre-commit-config.yaml`, `pyproject.toml` and `RUNNER_TOOLS`
- **THEN** every local hook passes

### Requirement: The runner tools table names each tool that the gate and the hooks need
`RUNNER_TOOLS` in `devops_cli.roadmap.runner_tools` SHALL list each program that the runner image must hold, its source, why it is there, and the command that proves it runs. `NOT_IN_RUNNER` SHALL name each program that a step of the Job does not count on, with the reason. The module SHALL hold no tool version: the devtools image gives each version, and the `Dockerfile` pins that image by digest.

#### Scenario: A source of the gate needs a program that is in neither table
- **WHEN** a program of a `devops ci` row, of a hook of `.pre-commit-config.yaml`, of a required job of `ci.yml` or of a live-marked test is in neither `RUNNER_TOOLS` nor `NOT_IN_RUNNER`
- **THEN** a test fails and names the program

#### Scenario: A Dockerfile pin bump changes no runner code
- **WHEN** a pull request moves the tag and the digest of the devtools image in `Dockerfile`
- **THEN** it changes no line of `src/devops_cli/roadmap/runner_tools.py`, because `RUNNER_TOOLS` holds no version

## REMOVED Requirements

### Requirement: The runner stage holds the tools of a step
**Reason**: The runner image builds FROM the devtools image, which gives the tools. `runner-deps` no longer installs apt packages or copies `runner-tools` (#4361).
**Migration**: The requirement "The runner image builds FROM the devtools image" holds the rule.

### Requirement: The runner stage deletes what only the build needs
**Reason**: The runner holds npm of the devtools image, which the `audit` row needs, and the Python of the devtools image has no pip (#4361).
**Migration**: The requirement "The runner image holds no uv cache and no build input" holds the rule.

### Requirement: The build of the runner image fails on a missing tool
**Reason**: The build no longer runs the tool check, so a change of `src/` does not run it again. The smoke test runs it on the loaded image (#4361).
**Migration**: The requirement "The runner tool check fails on a missing tool" holds the rule.

### Requirement: The smoke test of the runner image uses the table and bounds the image size
**Reason**: The devtools image is 4.88 GB, so the bound of 3000000000 bytes cannot hold (#4361).
**Migration**: The requirement "The smoke test of the runner image runs the tool check and bounds the size" holds the rule.

### Requirement: The runner image passes the image scan
**Reason**: The Go binaries of the devtools tools hold fixed HIGH and CRITICAL findings at their newest release, so no change in this project can pass a gate. The owner made the scan of these images report-only on 2026-11-19 (#4361).
**Migration**: The requirement "The scan of the runner image reports and stops no build" holds the rule, and SECURITY.md (Dedicated Development Resources and Sandboxes) records the exception.

## ADDED Requirements

### Requirement: The runner image builds FROM the devtools image
The `runner` stage SHALL build from `runner-deps`, which builds FROM the devtools image, pinned by tag and digest. `runner-deps` SHALL add the user `devops` (uid and gid 1000) and install the runtime and dev requirements of the `lock` stage into `/app/.venv`. The devtools image SHALL give each other program of `RUNNER_TOOLS`. The image SHALL run as user 1000 with `ENTRYPOINT ["devops"]` and `/app/.venv/bin` first on `PATH`.

#### Scenario: The image is built and started
- **WHEN** a person builds `--target runner` and runs `docker run --rm --entrypoint id <image> -u` and `docker run --rm <image> --version`
- **THEN** the build exits 0, the first command prints `1000`, and the second prints the version of devops-cli

### Requirement: The runner image holds no uv cache and no build input
The runner image SHALL hold no uv cache of root and no requirement file of the build. Each uv install of the `Dockerfile` SHALL keep its cache in a cache mount, and the requirement files of the `lock` stage SHALL come in as bind mounts.

#### Scenario: The image holds no uv cache
- **WHEN** a person runs `docker run --rm --user 0 --entrypoint sh <runner image> -c 'test -z "$(find /root/.cache/uv /lock -type f 2>/dev/null)"'`
- **THEN** the command exits 0

### Requirement: The runner tool check fails on a missing tool
The smoke test of the runner image SHALL run `python -m devops_cli.roadmap.runner_tools` as user 1000 on the loaded image. The check SHALL fail when a program is not on PATH or its version command exits non-zero. For a dev dependency and for the project, it SHALL also fail when the output lacks the version of the installed distribution. It SHALL compare no other version.

#### Scenario: A tool is missing or at another version
- **WHEN** a program of the table is not on PATH, its version command exits non-zero, or a dev dependency prints a version other than the version of its installed distribution
- **THEN** the check names the tool and exits 1

#### Scenario: A tool of the devtools image prints any version
- **WHEN** the version command of a tool that the devtools image gives exits 0
- **THEN** the check of the tool passes, and the check runs only that version command

#### Scenario: Every tool passes
- **WHEN** every version command exits 0, and each dev dependency prints its installed version
- **THEN** the check prints the number of tools and exits 0

### Requirement: The smoke test of the runner image runs the tool check and bounds the size
The smoke test of the runner image in `ci.yml` and in `release.yml` SHALL be the same text, SHALL run `python -m devops_cli.roadmap.runner_tools` on the loaded image, and SHALL fail when the image is larger than 7000000000 bytes. It SHALL run `uv run --locked devops ci --check --only openspec` in a copy of the checkout in the image. It SHALL hold no version command of its own for a tool of the table.

#### Scenario: The smoke test runs on the loaded image
- **WHEN** the Runner Image job of `ci.yml` runs its smoke test on the loaded image
- **THEN** the check module prints that every runner tool is on PATH and runs, and the step fails when `docker image inspect` reports more than 7000000000 bytes

#### Scenario: The OpenSpec of the image is not the version of the tools lock
- **WHEN** the devtools image holds an OpenSpec version that `tools.lock` does not pin, and the smoke test runs the OpenSpec gate in the image
- **THEN** the gate names the two versions and the step fails, so the split fails CI and not a live Job

### Requirement: The scan of the runner image reports and stops no build
The Runner Image jobs of `ci.yml` and `release.yml` SHALL scan the built `runner` target with `.github/actions/image-scan` (Trivy, `HIGH,CRITICAL`, fixed findings only) with exit code 0, and SHALL upload the SARIF under the category `trivy-image-runner`. SECURITY.md SHALL record the exception in its table, with the scope, the compensating control, the evidence, the approval and the review.

#### Scenario: The scan of a runner image with findings
- **WHEN** the Runner Image job scans a runner image whose devtools tools hold fixed HIGH findings
- **THEN** the scan step exits 0, the job log names each finding, and code scanning lists them under `trivy-image-runner`
