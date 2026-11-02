# Tasks

## 1. Type docker-py and delete its ignore markers

Reads: `src/devops_cli/docker/engine.py` (lines 225-330, 380-520), `src/devops_cli/docker/sdk.py` (lines 1-20), `src/devops_cli/sandbox/host.py` (lines 70-90), `src/devops_cli/commands/docker.py` (lines 170-185). Changes: `pyproject.toml`, `uv.lock`, `src/devops_cli/docker/engine.py`, `src/devops_cli/docker/sdk.py`, `src/devops_cli/sandbox/host.py`, `src/devops_cli/commands/docker.py`.

- [ ] 1.1 Verify the group with these commands, which give the same answer each time: `uv run devops ci typecheck`, `uv run devops ci deps`, `uv run devops ci lockfile`, `uv run devops ci test tests/docker tests/sandbox`, and `git grep -n -E "(import docker|from docker).*type: ignore" -- src` (it must print nothing; on the base it prints 9 lines)
- [ ] 1.2 Add `types-docker==7.2.0.20261006` after `types-psutil` in the `dev` list of `pyproject.toml`, add `requests==2.34.2` after `docker==7.2.0` in `dependencies`, run `uv lock`, then `uv sync --locked`
- [ ] 1.3 In `src/devops_cli/docker/engine.py`, catch `requests.HTTPError` (import `from requests import HTTPError` in the function, beside the docker import) at line 261, import `get_current_context_name` from `docker.context.config`, and return `cast("EngineClient", docker.DockerClient(**params))` from `_sdk_client`
- [ ] 1.4 Delete the 9 `# type: ignore[import-untyped]` markers on docker-py imports in `src/devops_cli/docker/engine.py` (6), `src/devops_cli/sandbox/host.py` (2) and `src/devops_cli/commands/docker.py` (1)
- [ ] 1.5 In the docstring of `src/devops_cli/docker/sdk.py`, replace the sentence "The SDK has no type information, so a type checker cannot hold `docker.DockerClient` to these Protocols." with the reason that the stubs list each keyword while the Protocols forward `**kwargs`, so `_sdk_client` casts and the contract suite holds the client to the Protocols

## 2. Lower the src type: ignore ceiling

Reads: `tests/invariants/test_architectural_invariants.py` (lines 170-200). Changes: `tests/invariants/test_architectural_invariants.py`.

- [ ] 2.1 Verify the group with `uv run devops ci test tests/invariants/test_architectural_invariants.py`; it passes at 40 only when group 1 is done, and it fails at 39
- [ ] 2.2 Set `DEFAULT_SUPPRESSION_CEILINGS["src type: ignore"]` to 40, the count that `_collect_suppressions` reports after group 1 (49 minus 9)

## 3. Split the image reference with docker-py's parser

Reads: `src/devops_cli/docker/registry.py` (lines 1-65), `tests/docker/test_registry_tag_digest.py` (lines 1-50). Changes: `src/devops_cli/docker/registry.py`, `tests/docker/test_registry_tag_digest.py`.

- [ ] 3.1 Write the failing tests first, then verify with `uv run devops ci test tests/docker/test_registry_tag_digest.py`. In the first table add a digest reference `ghcr.io/example/app@sha256:<64 hex digits>`, which splits into registry `ghcr.io`, repository `example/app` and the digest as the tag. In the refused table add `https://ghcr.io/example/app:v1` (a scheme), with the id `scheme`. On the base the digest row returns a wrong repository, and the scheme row raises nothing, so both fail
- [ ] 3.2 In `tagged_image`, import `resolve_repository_name`, `InvalidRepository` and `parse_repository_tag` inside the function (a module-level import breaks `tests/commands/test_cli_startup_imports.py`), replace the `partition` and `rpartition` split, refuse with the "no registry host" message when the remote name equals the repository, refuse with the "no tag" message when the tag is empty, and raise `RegistryReadError` from `InvalidRepository`. Update the docstring of `tagged_image` and delete the sentence of the module docstring that says #2603 will move the split
- [ ] 3.3 Verify with `uv run devops ci test tests/docker tests/argo tests/commands/test_cli_startup_imports.py` and `uv run devops ci typecheck`; the old table tests pass with their expected values
