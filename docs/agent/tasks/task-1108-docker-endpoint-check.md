# Task: Docker Endpoint Check Covers the Endpoint the SDK Dials (#1108)

**Issue**: [#1108](https://github.com/dan-petty/devops-cli/issues/1108)
**Status**: Done
**Milestone**: v0.2.31
**Priority**: priority/p2-medium
**Scope**: scope/security

## Description

Refactor Docker daemon endpoint resolution and egress validation so that the checks cover the exact endpoint the SDK dials:
- Gather the daemon endpoint across ordered sources: `DOCKER_HOST`, `DOCKER_CONTEXT`, `currentContext` in `config.json`, and the default Unix socket.
- Normalise the endpoint via docker-py's `parse_host`.
- Validate network endpoints (`http`, `https`) against SSRF egress policies using `validate_service_url`, requiring `ai.allow_private_network` for private/TEST-NET targets.
- Provide a public `resolve_host() -> DockerEndpoint` pre-flight step returning structured model (`source`, `raw`, `base_url`, `params`).
- Build `DockerClient` directly from validated endpoint parameters rather than uncontrolled `docker.from_env()`.
- Eliminate brittle regex matching in `devops docker push` and delegate image reference validation to docker-py and the daemon while escaping progress text.
- Delete obsolete constants (`CONST_DOCKER_UNIX_SOCKET_PATH`, `CONST_DOCKER_UNIX_SOCKET_URL`, `CONST_DOCKER_HOST_ENV_VAR`, `CONST_DOCKER_NETWORK_HOST_SCHEMES`).
- Remove `_get_docker_client()` in TUI data providers and update documentation examples to use `get_engine().client()`.

## Acceptance Criteria

- [x] One shared fixture `docker_endpoint_env` in `tests/conftest.py` provides isolated test environment, unsets Docker environment variables, sets `allow_private_network: false`, and provides a `write_context` helper.
- [x] Parametrized endpoint table verifies uppercase schemes, bare address-and-port (`192.0.2.1:2375`), and loopback/TEST-NET endpoints are refused without building a client.
- [x] Permitted private network endpoints (`ai.allow_private_network: true`) normalise to `http://...` and reach `DockerClient`.
- [x] Context resolution respects precedence (`DOCKER_HOST` > `DOCKER_CONTEXT` > `currentContext` > default socket) and raises `DockerDaemonUnavailableError` on missing contexts.
- [x] Environment TLS configurations (`DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH`) upgrade context endpoints to `https://...`.
- [x] CLI `devops docker images` prints single error line naming source and reason with no traceback on invalid endpoints.
- [x] Pre-flight docstring on `resolve_host()` documents the pre-flight check and the DNS window.
- [x] `devops docker push` accepts registry ports (`localhost:5000/app:1.0`, `example.com:443/a/b:c`, `[::1]:5000/app:1`), escapes progress markup, and handles `InvalidRepository` and `APIError`.
- [x] Zero construct remnants for deleted constants, `replace("tcp://", ...)`, `docker.from_env(`, and `re.match` in `commands/docker.py`.
- [x] Changelog fragment `changelog.d/1108.md` is provided.

## Deliverables

- [x] `src/devops_cli/config/constants.py`: deleted deprecated Docker constants.
- [x] `src/devops_cli/models/docker.py` and `src/devops_cli/models/__init__.py`: added frozen `DockerEndpoint` model.
- [x] `src/devops_cli/docker/engine.py`: implemented `_gather_endpoint`, `_parse_endpoint`, `_check_endpoint_egress`, `resolve_host`, `unix_socket_path`, and `client`.
- [x] `src/devops_cli/commands/docker.py`: updated `_engine` error printing (`safe=True`), and updated `push` for registry ports, markup escaping, and error handling.
- [x] `src/devops_cli/ui/data_providers.py`: deleted `_get_docker_client()`, updated `fetch_docker_status` to use `get_engine().client()`.
- [x] `src/devops_cli/ai/knowledge_base/devops_cli/libraries/docker.md`: updated client initialization examples.
- [x] `tests/conftest.py`: added `docker_endpoint_env` fixture.
- [x] `tests/test_docker_engine.py`: updated Section 1 with contract tests, parametrized endpoint table, context tests, and CLI error handling tests.
- [x] `tests/test_docker.py`: patched `DockerClient`, mocked 400 `APIError`, added registry port, progress escaping, and repository error tests.
- [x] `tests/test_ui_dashboard.py`: updated Docker status provider tests to drive `DockerEngineService.client`.
- [x] `changelog.d/1108.md`: changelog fragment.
- [x] `docs/agent/tasks/task-1108-docker-endpoint-check.md`: task tracking file.
