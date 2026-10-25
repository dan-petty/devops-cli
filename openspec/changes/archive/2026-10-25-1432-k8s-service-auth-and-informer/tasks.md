# Tasks

## 1. Proxy Authentication Headers and Token Refresh

- [x] 1.1 Write failing tests in `tests/test_k8s_service_proxy.py` verifying that bearer tokens yield `Authorization: Bearer <token>` without `BearerToken`, client certificates keep working, and `refresh_api_key_hook` executes on each request (`uv run devops ci test tests/test_k8s_service_proxy.py`).
- [x] 1.2 Implement `_auth_headers` in `src/devops_cli/k8s/service_proxy.py` using `configuration.auth_settings()` after executing `refresh_api_key_hook` (`uv run devops ci test tests/test_k8s_service_proxy.py`).
- [x] 1.3 Update connection check documentation in `SECURITY.md` and `README.md`, and sync docs with `uv run devops docs generate --sync-readme`.

## 2. Typed Informer Watch Streaming and FakeCoreV1 Updates

- [x] 2.1 Write failing tests in `tests/test_k8s_service.py` asserting that namespaced and all-namespace watches yield typed `V1Pod` models, and update `tests/k8s_fakes.py` to support watch streaming with `:rtype: V1PodList` (`uv run devops ci test tests/test_k8s_service.py`).
- [x] 2.2 Update `PodInformer.stream_events` in `src/devops_cli/k8s/informer.py` to pass typed list functions directly to `w.stream` without lambda wrappers, recording the latest `resourceVersion` (`uv run devops ci test tests/test_k8s_service.py`).

## 3. Informer Reconnection Backoff and 410 Gone Relisting

- [x] 3.1 Write failing tests in `tests/test_k8s_service.py` covering persistent error exponential backoff, reconnecting with the last `resourceVersion`, and relisting upon 410 Gone (`uv run devops ci test tests/test_k8s_service.py`).
- [x] 3.2 Implement `_run_watch_loop` exponential backoff via `tenacity` and 410 Gone relisting in `src/devops_cli/k8s/informer.py` (`uv run devops ci test tests/test_k8s_service.py`).
- [x] 3.3 Run static analysis and full verification suite (`uv run devops ci`).

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
