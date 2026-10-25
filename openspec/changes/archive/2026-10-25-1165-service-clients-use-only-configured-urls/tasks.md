# Tasks

## 1. AI Endpoint Resolver and Fallback Removal

- [x] 1.1 Write failing tests asserting AI endpoint resolution across configured providers and failure when unconfigured (`uv run devops ci test tests/test_ai_endpoints.py`)
- [x] 1.2 Implement `resolve_ai_endpoint` in `src/devops_cli/ai/endpoints.py` and integrate across AI callers, removing hard-coded `http://localhost:11434` fallbacks and duplicate URL constants (`uv run devops ci test tests/test_ai_endpoints.py`)
- [x] 1.3 Sync documentation with `uv run devops docs generate --sync-readme`

## 2. Service URL Settings and Fallback Removal

- [x] 2.1 Write failing tests verifying service URL settings have no code defaults and `config.example.yaml` holds suggested URLs (`uv run devops ci test tests/test_service_url_defaults.py`)
- [x] 2.2 Update `Settings` service URL fields to default to `None` or empty list, update `config.example.yaml`, and remove hard-coded loopback fallbacks for Qdrant, Tempo, Pyroscope, and Vault (`uv run devops ci test tests/test_service_url_defaults.py`)
- [x] 2.3 Sync documentation with `uv run devops docs generate --sync-readme`

## 3. Embedding Benchmark Default Model and Non-Zero Failure

- [x] 3.1 Write failing tests verifying the embedding benchmark defaults to the configured embedding model and exits non-zero without saving failed runs (`uv run devops ci test tests/test_embedding_benchmark.py`)
- [x] 3.2 Update `commands/benchmark.py` and `embedding_runner.py` to default to the configured embedding model, select provider by configuration only, and exit non-zero when all requests fail (`uv run devops ci test tests/test_embedding_benchmark.py`)
- [x] 3.3 Sync documentation with `uv run devops docs generate --sync-readme`

## 4. Deploy-Stack URL Configuration on Empty Settings

- [x] 4.1 Write failing tests verifying `devops k8s deploy-stack` sets service URLs when empty, never overwrites existing values, and lists writes in `--dry-run` (`uv run devops ci test tests/test_k8s_deploy_stack_urls.py`)
- [x] 4.2 Update `deploy-stack` and its dry-run output to configure deployed service URLs only when settings are empty (`uv run devops ci test tests/test_k8s_deploy_stack_urls.py`)
- [x] 4.3 Sync documentation with `uv run devops docs generate --sync-readme`

## 5. ast-grep Invariant Guard and Quality Gates

- [x] 5.1 Add ast-grep invariant rule `net-localhost-fallback` and test cases verifying rejection of localhost fallback expressions in `src/` (`uv run ast-grep test`)
- [x] 5.2 Verify all tests and static analysis pass (`uv run devops ci`)
- [x] 5.3 Sync documentation with `uv run devops docs generate --sync-readme`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
