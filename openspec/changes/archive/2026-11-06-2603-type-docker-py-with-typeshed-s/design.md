# Design

## Decisions

- **Add `types-docker==7.2.0.20261006` to the `dev` group.** typeshed maintains it, and it matches docker 7.2.0. It removes the need for the 9 markers.
- **Declare `requests==2.34.2` in `dependencies`.** The fix of the exception type at `engine.py` line 261 imports `requests.HTTPError`. deptry rule DEP003 refuses a transitive import. `requests` is already installed and locked through docker-py, so no new package arrives.
- **Catch `requests.HTTPError` at `engine.py` line 261.** `Response.raise_for_status` raises only `HTTPError`, and `create_api_error_from_http_exception` takes only that type in the stubs. The catch now matches the call that it guards.
- **Import `get_current_context_name` from `docker.context.config`.** The stubs have it only there. At run time the two names are the same function, so no marker is needed. This removes the tenth marker that the issue kept.
- **Cast the SDK client in `_sdk_client`.** `cast("EngineClient", docker.DockerClient(**params))` keeps the Protocol as the seam for fakes. The contract suite `tests/docker/test_engine_contract.py` holds the real client and the fake to the same calls. The docstring of `sdk.py` is updated: it says the stubs list each keyword while the Protocols forward `**kwargs`, so mypy cannot hold the client to them.
- **Lower the ceiling to 40.** The measured count is 49. Removing 9 markers gives 40. The ratchet test compares `total > ceiling`, so the group that lowers it follows the group that removes the markers.
- **Split the reference with `parse_repository_tag` and `resolve_repository_name`, imported inside `tagged_image`.** A module-level import of docker-py breaks the startup budget of `devops argo --help`. A reference is refused as "no registry host" when `resolve_repository_name` returns a remote name equal to its input. It is refused as "no tag" when the tag is empty. `InvalidRepository` becomes `RegistryReadError`.
- **A digest reference splits into the repository and the digest.** docker-py reads `<image>@sha256:...` as repository and digest. The old split gave a wrong repository. This is a consequence of the parser. One table row pins it.

## Rejected alternatives

- **Keep `except Exception` at line 261 and add a marker.** It adds a marker to the ceiling. The stub types the parameter as `HTTPError`, so the narrow catch is the fix.
- **Align the Protocols of `sdk.py` with the stubs (the proposed design of the issue).** Mypy shows 5 members in conflict because a Protocol method with `**kwargs: Any` does not match a stub method with named keyword-only parameters. The callers (`create_container(**create_kwargs)`, `images.build(**kwargs)`) pass keywords through. Alignment would copy about 70 parameters of `containers.create` into the project and would give up the pass-through. The cast needs no marker and keeps the seam.
- **Add markers for the 5 Protocol conflicts.** It adds 5 markers to the ceiling.
- **Keep one `type: ignore[attr-defined]` at line 393.** The stubs have the name in `docker.context.config`, so no marker is needed.
- **Resolve a reference without a host to `docker.io` (the earlier plan).** It breaks the existing refusal test and the rule "same TaggedImage as before". A reference with no host names no registry to ask, so the refusal stays.
- **Import docker-py at the top of `registry.py`.** It fails `tests/commands/test_cli_startup_imports.py`.
- **Keep the 10-line hand-rolled split.** The purpose of the item is to use the typed parser.
