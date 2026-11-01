# Design

## Decisions

- **Add types-docker==7.2.0.20261006 to the dev dependency group**: It types docker-py 7.2.0 imports, removes the need for 8 import-untyped markers, and frees ceiling budget for new code.
- **Narrow the except clause at engine.py line 261 from Exception to requests.HTTPError**: The stub types create_api_error_from_http_exception with a requests.HTTPError parameter. Narrowing the catch matches the stub and removes the need for a type ignore.
- **Align the 5 Protocol member types in sdk.py with the types-docker stubs**: DockerClient must satisfy EngineClient for the type checker. Aligning the types at the source removes the 5 conflicts and keeps the Protocol as the seam for fakes.
- **Keep one # type: ignore[import-untyped] on the get_current_context_name import**: The stub genuinely lacks docker.context.api.get_current_context_name. A single targeted marker is the correct suppression.
- **Lower the ceiling from 51 to 42**: 51 minus the 9 removed markers equals 42. The ceiling must reflect the actual count.
- **Use docker-py's parse_repository_tag and resolve_repository_name in tagged_image**: With types-docker installed, the import is typed and adds no marker. It replaces the 10-line hand-rolled split and is the standard parser for distribution references.
- **Resolve references without a registry host to docker.io**: resolve_repository_name adds the default registry docker.io for references that name no host. This is the standard behavior of the distribution reference grammar and matches crane and docker pull.

## Rejected alternatives

- **Keep except Exception and add a type ignore at line 261**: It adds a marker to the ceiling instead of removing one. The stub types the parameter as requests.HTTPError, so narrowing is the correct fix.
- **Add type ignores for the 5 Protocol conflicts in engine.py**: It adds 5 markers to the ceiling instead of removing 9. Aligning the Protocols in sdk.py removes the conflicts at the source.
- **Remove the get_current_context_name call and use an alternative**: get_current_context_name is the only way to read the current context name from docker-py's config. No alternative exists in the stubs.
- **Keep the 10-line hand-rolled split in registry.py**: The purpose of this item is to use the typed parser and free ceiling budget. The hand-rolled split was a workaround for the missing type hints.
