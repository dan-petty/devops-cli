# Tasks

## 1. Pin the devcontainer feature releases and guard them with invariant cases

Kind: other. Reads: `.devcontainer/image/devcontainer.json`, `.devcontainer/image/devcontainer-lock.json`, `.devcontainer/devcontainer.json`, `tests/invariants/test_devcontainer_config.py`, `src/devops_cli/tools_lock/tools.lock`. Changes: `.devcontainer/image/devcontainer.json`, `tests/invariants/test_devcontainer_config.py`.

- [x] 1.1 Write the new cases of `tests/invariants/test_devcontainer_config.py` first: one case fails on each feature option whose value is `latest` in a config under `.devcontainer/`, one case fails on a `docker-in-docker` feature whose options name no Compose release, and one case fails on a feature that the lockfile beside its config does not hold with a `resolved` digest; a fourth case proves that the message of one config with two violations holds both feature ids and both option names. Then pin the options of `.devcontainer/image/devcontainer.json`: kubectl to 1.37.2 and Helm to 4.3.2, the versions that `src/devops_cli/tools_lock/tools.lock` pins, and the Docker, Compose and Minikube releases to the newest stable release that each publisher names, with the exact option names taken from the metadata of each feature
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py` passes

## 2. Document the pinned feature releases and their bump

Kind: other. Reads: `.devcontainer/image/devcontainer.json`, `docs/DEVCONTAINER_USAGE.md`. Changes: `docs/DEVCONTAINER_USAGE.md`.

- [ ] 2.1 Add a sentence to the pre-installed tooling section of `docs/DEVCONTAINER_USAGE.md` that names the pinned releases of the `docker-in-docker` and `kubectl-helm-minikube` features, says that kubectl and Helm follow the pins of the tools lock, and says that a bump changes the image config in the same pull request as the lockfile
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `docs/DEVCONTAINER_USAGE.md` to name the pinned feature releases and the step that bumps them
  - Verification: `$ uv run devops ci docs` passes
