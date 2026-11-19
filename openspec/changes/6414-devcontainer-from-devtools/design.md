# Design

## Decisions
- The devtools image is pinned once, in `.devcontainer/Dockerfile`, with its date tag and its digest. The date tag stays on the registry, so the digest has a tag that names it. Renovate's dockerfile manager moves both, and the `devtools` group puts each reference of the image in one pull request.
- The build action needs the Dev Containers CLI before the image exists. The `devcontainers-cli` stage copies only the CLI package of the devtools image, and `docker buildx build --target devcontainers-cli --output type=local` puts it on the runner. So the CLI comes from the digest that the Dockerfile pins, with no second copy of the digest, and the pull of the devtools layers fills the cache of the builder for the image build. The CLI package has no dependencies, so the Node.js of `setup-node` runs it.
- The smoke action copies the CLI from the image that it starts, because the image is FROM devtools and `devcontainer up` pulls it anyway.
- The venv is the last directory of `PATH`, so `python` and `python3` stay the system Python, and only commands that the system does not have, such as `devops`, come from the venv. The venv uses `/usr/bin/python3`, and the copy of the project names `python3.*`, so the Dockerfile copies no Python minor.
- The project stage installs the project into the venv, and the last stage copies only the package, its dist-info and its console script with `COPY --link --parents`, as the root `Dockerfile` does.
- `USER vscode` is the last instruction. The `common-utils` Feature makes the user after the Dockerfile stages, and the Dev Containers CLI sets `USER root` for the Feature installs and the image user after them.
- The `GIT_CONFIG_*` entries go to `remoteEnv`. The Dev Containers CLI writes `containerEnv` as `ENV` lines, which gave the `SecretsUsedInArgOrEnv` warnings; `remoteEnv` is in the metadata label only. Each process that the Dev Containers tools start gets it, and the smoke action checks the order of the helpers through `devcontainer exec`.
- `DOCKER_HOST=unix:///var/run/docker.sock` is in `remoteEnv`, so a bash login shell that reads `/etc/profile.d/podman-docker.sh` keeps the rootful socket that the Docker SDK of devops-cli needs.
- The `upgradePackages` option of `common-utils` stays `true`: the image build takes the security updates of sid since the devtools build.
- The smoke action runs `devcontainer up` with no `--skip-post-create`, so the post-start check of the `podman-in-podman` Feature runs and waits for the rootful API service.

## Rejected alternatives
- `devcontainers/ci`: it pushes tags and has no push-by-digest output and no `--metadata-file` pass-through (docs/github-action.md of devcontainers/ci), so the release cannot start the digest before it tags it.
- A job container of the devtools image: the build needs Docker Buildx for the SBOM, the provenance, push-by-digest and the metadata file, and the devtools image has no Docker CLI. Podman builds have none of these outputs.
- `npm ci` of `src/devops_cli/tools_lock/devcontainers-cli` in the actions: it keeps a second pin of the CLI in this repository, which #4363 removes, while the devtools image already holds the CLI.
- A second reference of the devtools digest in the workflows: two copies of one pin, where the Dockerfile stage gives the CLI from one.
- `# check=error=true` alone for the Dev Containers CLI build: the CLI puts `ARG _DEV_CONTAINERS_BASE_IMAGE=scratch` before the user Dockerfile, so the directive applies to a plain build of the file only. The move of the `GIT_CONFIG_*` entries removes the warnings of the CLI build.
