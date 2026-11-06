# Proposal

## Why

docker-py 7.2.0 ships no type hints. Nine imports in `src` carry `# type: ignore[import-untyped]`, and they count toward the `src type: ignore` ceiling (#2603). typeshed publishes `types-docker` for this version. With the stubs, mypy reports the nine markers as unused. The project can then delete them, lower the ceiling, and import docker-py's reference parser with a type. The reference split in `tagged_image` (`src/devops_cli/docker/registry.py`, #1997) can then use that parser.

## What Changes

- Add `types-docker==7.2.0.20261006` to the `dev` group in `pyproject.toml`. Add `requests==2.34.2` to `dependencies`, because the fix of `engine.py` line 261 imports `requests` (see Feasibility). `uv lock` updates `uv.lock`.
- In `src/devops_cli/docker/engine.py`: catch `requests.HTTPError` at line 261, import `get_current_context_name` from `docker.context.config` (the stubs have it there), and make `_sdk_client` return `cast("EngineClient", docker.DockerClient(**params))`.
- Delete the 9 `# type: ignore[import-untyped]` markers on docker-py imports: 6 in `engine.py`, 2 in `src/devops_cli/sandbox/host.py`, 1 in `src/devops_cli/commands/docker.py`. No docker-py marker stays.
- Lower `DEFAULT_SUPPRESSION_CEILINGS["src type: ignore"]` in `tests/invariants/test_architectural_invariants.py` from 51 to 40, the new count.
- `tagged_image` uses `docker.utils.parse_repository_tag` and `docker.auth.resolve_repository_name`. It keeps its refusals. A reference that docker-py rejects (a scheme such as `https://`, or an index name with a hyphen at an end) is a `RegistryReadError`. A reference with a digest (`<image>@sha256:...`) now splits into the repository and the digest as the tag; the old split gave a wrong repository for it.
- The change has no spec delta (`skip_specs: true`). It is a typing and refactor change. The messages and exit codes that a consumer sees stay as they are: `argo-image-pin-drift` names no reference form, and a refused reference was and is a `RegistryReadError` that `check_pins` shows as a pin that was not read.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/docker/engine.py`, `src/devops_cli/docker/sdk.py` (docstring only), `src/devops_cli/docker/registry.py`, `src/devops_cli/sandbox/host.py`, `src/devops_cli/commands/docker.py`
- Dependencies: `pyproject.toml`, `uv.lock`
- Tests: `tests/invariants/test_architectural_invariants.py`, `tests/docker/test_registry_tag_digest.py`
- Reused and kept passing: the `EngineClient` Protocols of `src/devops_cli/docker/sdk.py` (#1316, #2534) and their contract suite `tests/docker/test_engine_contract.py`; the ratchet `test_suppressions_stay_under_their_ceilings`; the startup budget test `tests/commands/test_cli_startup_imports.py`; `check_pins` in `src/devops_cli/argo/image_pins.py`, which catches `RegistryReadError`.

## Acceptance

- `uv run mypy src` passes with `types-docker` installed, and the ceiling is lower than 51: group 1 (mypy) and group 2 (ceiling 40).
- No `# type: ignore[import-untyped]` names a docker-py module: group 1.
- `tagged_image` uses docker-py's parser, and its table tests still pass: group 3.

## Feasibility

All checks ran on 2026-11-01 on `origin/main` (0d2d0723) with Python 3.14.

- The 9 markers exist. `git grep -n "type: ignore" -- src | grep -E "docker|sandbox/host"` lists `commands/docker.py:175`, `docker/engine.py:242,267,313,393,439,503` and `sandbox/host.py:78,79`.
- The stubs behave as the issue says. After `uv pip install types-docker==7.2.0.20261006` in the worktree, `uv run mypy src` printed "Found 12 errors in 3 files": 9 "Unused type: ignore" and 3 real errors (`engine.py:261` `Exception` is no `HTTPError`; `engine.py:315` `DockerClient` is no `EngineClient`; `engine.py:393` no `get_current_context_name` in `docker.context.api`).
- The issue says the ceiling "sits at its value". That is wrong. `_collect_suppressions` reports 49 `src type: ignore` markers against a ceiling of 51. So new code could add two markers today. Removing the 9 gives 40, so the ceiling goes to 40, not 42. The ceiling test is `total > ceiling`, so the ceiling must go down after the markers go, not before.
- Line 393 needs no marker. The stubs have the name in `docker.context.config` (`docker-stubs/context/config.pyi`), and `docker.context.api.get_current_context_name is docker.context.config.get_current_context_name` prints `True`. So the import moves and the tenth marker the issue kept is not needed.
- The issue says to align the Protocols of `sdk.py` with the stubs. That cannot work. A Protocol method with `**kwargs: Any` does not match a stub method with named keyword-only parameters (mypy shows this for `APIClient.get`, `prune_builds`, `ContainerCollection.create`, `ImageCollection.build`, `NetworkCollection.create` and `VolumeCollection.list`). The callers pass `**create_kwargs` through, so the Protocol must accept any keyword. Listing every keyword of `containers.create` would copy about 70 stub parameters into the project. The seam stays: `_sdk_client` casts, and `tests/docker/test_engine_contract.py` holds the SDK client and the fake to the same calls, as the docstring of `sdk.py` already says. With these two edits (`cast`, `docker.context.config`) and the exception change, `uv run mypy src` printed "Success: no issues found in 629 source files".
- The `requests.HTTPError` change needs `requests` declared. `uv run deptry src` printed "DEP003 'requests' imported but it is a transitive dependency". `requests` 2.34.2 is already in `uv.lock` through docker-py, so declaring it adds no package. After the edit, `uv run devops ci deps` and `uv run devops ci lockfile` passed.
- The import of docker-py in `registry.py` must be lazy. At module level it fails `tests/commands/test_cli_startup_imports.py` (`['argo', '--help']` imported 981 modules, over the budget), because `devops_cli.argo` imports `registry`. Inside `tagged_image` the test passes, as `engine.py` already imports docker-py inside functions.
- The docker-py parser keeps the refusals of the old split. On this tree `parse_repository_tag("nginx:1.27")` gives `("nginx", "1.27")` and `resolve_repository_name("nginx")` gives `("docker.io", "nginx")`, with the remote name equal to the input. That equality tells that no host was named. `docker.io/library/nginx:1` gives `("docker.io", "library/nginx")`. The old behavior also stays for `localhost:5000/team/app:v1` and `localhost/app:v1`. I applied all of this in a scratch copy: `uv run devops ci test tests/docker tests/argo tests/commands/test_cli_startup_imports.py` printed "185 passed", and `uv run devops ci test tests/invariants/test_architectural_invariants.py` passed with the ceiling at 40. I then reverted the copy.
- The old plan added a rule that `org/img:tag` resolves to `docker.io`. That breaks `test_a_reference_without_a_registry_host_or_a_tag_is_refused` (cases `no-registry` and `hub-path`) and contradicts "same TaggedImage as before". The rule is removed.
- `resolve_repository_name` raises `docker.errors.InvalidRepository` for `https://ghcr.io/example/app` ("Repository name cannot contain a scheme"). The old split accepted this input and returned a wrong registry (`https:`). The plan maps the error to `RegistryReadError`, because `check_pins` catches only that class.
- Nothing newer did this work. `git log --oneline -3 -- src/devops_cli/docker/engine.py src/devops_cli/docker/registry.py` shows #2845, #2605 and #2588 as the latest, and none touches docker-py typing. `gh api search` for `types-docker`, `docker-py` and `import-untyped` finds only #2603 and its plan pull request. #1997 is closed. The open issue #2610 uses `tag_digest` and keeps one reference split in `docker/registry.py`, so it does not conflict.
- The test path in the earlier plan, `tests/test_architectural_invariants.py`, does not exist. The file is `tests/invariants/test_architectural_invariants.py`. The table tests are in `tests/docker/test_registry_tag_digest.py` (it exists).

## Existing Tool Considered

typeshed's `types-docker` (7.2.0.20261006) covers the need. Typeshed maintains it with the types of docker-py 7.2.0. For the reference split, docker-py's own `parse_repository_tag` and `resolve_repository_name` replace the hand-rolled split. Nothing new is built. The change deletes 9 ignore markers and the hand-rolled split of `tagged_image` (about 10 lines).
