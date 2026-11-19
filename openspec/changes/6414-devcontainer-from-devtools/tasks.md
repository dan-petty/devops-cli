# Tasks

## 1. Image build definition

- [x] 1.1 Build `.devcontainer/Dockerfile` FROM the devtools digest with the `lock`, `venv`, `project` and `devcontainers-cli` stages, the project as the last layer, `USER vscode` and `# check=error=true`; delete the actionlint, tools and npm-tools stages, the tool venvs, the `/etc/os-release` rewrite and the pre-commit install
  - Verification: `$ ! git grep -n -E 'curl|sha256sum|npm ci|devops-tools|os-release|FROM (debian|node|docker.io)' -- .devcontainer/Dockerfile`
- [x] 1.2 Keep only `common-utils:2` and `podman-in-podman:1` with `dockerCompat` in `.devcontainer/image/devcontainer.json`, move the `GIT_CONFIG_*` entries to `remoteEnv` with `DOCKER_HOST`, remove `DOCKER_CLI_HINTS`, and write `devcontainer-lock.json` again with `devcontainer upgrade`
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py tests/core/test_third_party_telemetry.py tests/invariants/test_uv_malware_check.py`
- [x] 1.3 Delete the pin-comparison test of `tests/invariants/test_devcontainer_config.py` and lower its count in `tests/gate/tree_checks/config_reads.toml`
  - Verification: `$ uv run devops ci --check --only test-tree`

## 2. Workflows and actions

- [ ] 2.1 Build with the CLI of the `devcontainers-cli` stage, start with the CLI of the image, add the smoke checks of the venv, the tools, Podman, the API socket and the credential helpers, and remove the `devops install-tools` steps and the uv steps that only they needed
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [ ] 2.2 Remove the `tools_lock` path filter of `devcontainer-image.yml`, and give the step that calls the smoke action `timeout-minutes`
  - Verification: `$ ! git grep -n 'tools_lock' -- .github/workflows/devcontainer-image.yml`
- [ ] 2.3 Change the release test to the release jobs with no uv steps
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py`

## 3. Renovate

- [ ] 3.1 Group `ghcr.io/dan-petty/devtools` for each manager, remove the Python-minor custom manager of `.devcontainer/Dockerfile`, and rewrite the descriptions that name devcontainer copies
  - Verification: `$ docker run --rm -v "$PWD:/repo:ro" -w /repo --entrypoint renovate-config-validator ghcr.io/renovatebot/renovate:44.239.2 --strict --no-global .github/renovate.json`

## 4. Documents

- [ ] 4.1 Describe the devtools base, Podman, the two image stores, `DOCKER_HOST`, the inotify risk, the `devcontainer upgrade` step and `remoteEnv` in `docs/DEVCONTAINER_USAGE.md`, the path filter in `docs/SDLC.md`, Podman in place of Docker-in-Docker in the knowledge base, the Purpose of the `devcontainer-image-tools` spec, and the source of the keyring packages in `src/devops_cli/config/constants.py`
  - Verification: `$ git grep -n 'devcontainer upgrade' docs/DEVCONTAINER_USAGE.md`

## Workflow follow-up

- The docker driver of Minikube with `podman-docker` in the devcontainer is not tested: #6466.
- The image smoke steps of `ci.yml` and `release.yml` use `--tmpfs <path>:uid=1000,gid=1000`, which Podman refuses, so they do not run in the devcontainer: #6468.
- The Feature layers sit on the project layer, so a change of `src/` builds them again: #6470.
- Pending a person: rebuild the devcontainer on the rootless Podman host (WSL2, `--userns=keep-id`) after the release, and run `docker version`, `podman run --rm quay.io/podman/hello` and `devops docker images` there: #6471.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
