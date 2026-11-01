# Tasks

## 1. Add types-docker to dev dependencies

Reads: none. Changes: `pyproject.toml`.

- [ ] 1.1 uv run mypy src reports 9 unused import-untyped ignores and 3 new errors in engine.py after types-docker is installed, and verify that `uv sync && uv run mypy src 2>&1 | head -30` fails on the base
- [ ] 1.2 Add types-docker==7.2.0.20261006 to the [dependency-groups] dev list in pyproject.toml, after types-psutil, and verify that `uv sync && uv run mypy src 2>&1 | head -30` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Fix the 3 mypy errors and remove unused ignores

Reads: none. Changes: `src/devops_cli/docker/engine.py`, `src/devops_cli/docker/sdk.py`, `src/devops_cli/sandbox/host.py`, `src/devops_cli/commands/docker.py`.

- [ ] 2.1 uv run mypy src exits with code 0 and no # type: ignore[import-untyped] names a docker-py module, and verify that `uv run mypy src` fails on the base
- [ ] 2.2 In engine.py: narrow the except clause at line 261 from Exception to requests.HTTPError. In sdk.py: align the 5 Protocol member types (api, containers, images, networks, volumes) with the types-docker stubs so DockerClient satisfies EngineClient. In engine.py: keep one # type: ignore[import-untyped] on the get_current_context_name import. Remove the 8 other unused # type: ignore[import-untyped] markers from engine.py, sandbox/host.py, and commands/docker.py, and verify that `uv run mypy src` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Lower the src type: ignore ceiling to 42

Reads: none. Changes: `tests/test_architectural_invariants.py`.

- [ ] 3.1 The ceiling assertion in test_architectural_invariants.py passes with the value 42, and verify that `uv run pytest tests/test_architectural_invariants.py -k ceiling` fails on the base
- [ ] 3.2 Change DEFAULT_SUPPRESSION_CEILINGS['src type: ignore'] from 51 to 42 in tests/test_architectural_invariants.py, and verify that `uv run pytest tests/test_architectural_invariants.py -k ceiling` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Use docker-py's parser in tagged_image

Reads: none. Changes: `src/devops_cli/docker/registry.py`.

- [ ] 4.1 The existing table tests of tagged_image in tests/docker/test_registry_tag_digest.py pass with the same expected TaggedImage values, and a new test confirms org/img:tag resolves to registry docker.io, and verify that `uv run pytest tests/docker/test_registry_tag_digest.py` fails on the base
- [ ] 4.2 In tagged_image, replace the hand-rolled partition and rpartition logic with docker.utils.parse_repository_tag and docker.auth.resolve_repository_name. Import both from docker.utils and docker.auth. A reference without a registry host resolves to docker.io via resolve_repository_name. Keep the RegistryReadError for references that name no tag, and verify that `uv run pytest tests/docker/test_registry_tag_digest.py` passes
- [ ] 4.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
