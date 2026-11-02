# Design

## Decisions

- **Refuse `GOFLAGS`, `YARN_YARN_PATH` and `UV_ENV_FILE` by adding them to `CONST_CODE_LOADING_ENV_PATTERNS`.**: `_is_env_override_refused` already raises `SecurityError` for a pattern match, so the change needs no new guard code.
- **Keep `UV_TOOL_DIR` and `npm_config_cache` accepted.**: Both name directories. They start no caller-named program. Refusing them blocks legitimate use without a security gain.
- **Record no live probe for `go` and `yarn`.**: The devcontainer has no `go` and no `yarn`. The tests reach no network and start no real tool.
- **Test the guard offline with `build_subprocess_env`.**: The test doubles only the process edge and asserts the `SecurityError`.

## Rejected alternatives

- **Refuse all five keys.**: `UV_TOOL_DIR` and `npm_config_cache` name directories. `ARCHITECTURE.md` says `npm_config_cache` stays accepted because `devops install-tools` sets it.
- **Document all five keys as safe.**: `GOFLAGS` carries `-toolexec`, `YARN_YARN_PATH` names a JavaScript file, and `UV_ENV_FILE` names a file that uv sources. The issue names these as code-loading paths.
- **Add a live probe test.**: Tests reach no network and no real scanner. The devcontainer has no `go` and no `yarn`.
- **Add a new guard function.**: `_is_env_override_refused` already checks `CONST_CODE_LOADING_ENV_PATTERNS`. A new function duplicates the existing path.
