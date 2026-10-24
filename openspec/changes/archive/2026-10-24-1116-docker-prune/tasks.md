# Tasks

## 1. Specced test client and failing tests

- [x] 1.1 Add autospecced `docker_client` fixture in `tests/conftest.py` and write failing tests in `tests/test_docker.py` and `tests/test_docker_engine.py` asserting attribute pinning and prune behavior, verified via `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Implement `DockerEngineService.prune` in `src/devops_cli/docker/engine.py` calling containers, networks, images, and conditionally volumes prune, verified via `uv run devops ci test tests/test_docker_engine.py`
- [x] 1.3 Update `devops docker prune` in `src/devops_cli/commands/docker.py` to use `_engine().prune()`, remove legacy tuple branch, update confirmation prompts, and handle errors cleanly, verified via `uv run devops ci test tests/test_docker.py`
- [x] 1.4 Update help strings in `src/devops_cli/lang/en/help.py`, update knowledge base in `src/devops_cli/ai/knowledge_base/it_domains/tools/docker.md`, regenerate documentation via `uv run devops docs generate --sync-readme`, and verify with `uv run devops docs check`
- [x] 1.5 Run full verification gate with `uv run devops ci`

## Workflow follow-up

- Pending a person: on the devcontainer's Docker engine, and on rootless Podman reached through `DOCKER_HOST`, run `devops docker prune --force` and `devops docker prune --force --volumes`. Before each run, create a stopped container, a dangling image, an unused network, an unused anonymous volume and an unused named volume. Record in the task file what was removed, whether the named volume and tagged images were kept, and the reported space.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
