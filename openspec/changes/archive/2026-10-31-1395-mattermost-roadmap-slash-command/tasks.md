# Tasks

## 1. Network Policies and Manifests

- [x] 1.1 Add failing tests for Mattermost egress to roadmap-service, roadmap-service ingress from Mattermost, and allowed untrusted internal connections in `tests/commands/k8s/test_k8s_network_policies.py` and `tests/test_k8s_roadmap_service.py`
- [x] 1.2 Update `k8s/mattermost/mattermost.yaml`, `k8s/mattermost/networkpolicy.yaml`, and `k8s/devops/roadmap-service/networkpolicy.yaml` and verify tests pass with `uv run pytest tests/commands/k8s/test_k8s_network_policies.py tests/test_k8s_roadmap_service.py`


## 2. Managed Credential and Cluster Secret

- [x] 2.1 Add failing tests for `mattermost.command_token` credential and cluster secret entry in `tests/security/test_config_declarations.py`, `tests/commands/test_config_audit_keys.py`, and `tests/k8s/test_cluster_secret_plan.py`
- [x] 2.2 Add `mattermost.command_token` to `src/devops_cli/config/env.py` and cluster secret in `src/devops_cli/k8s/cluster_secrets.py` and verify tests pass with `uv run pytest tests/security/test_config_declarations.py tests/commands/test_config_audit_keys.py tests/k8s/test_cluster_secret_plan.py`

## 3. Worker and ServiceManager Status Tracking

- [x] 3.1 Add failing unit tests for per-lane last-round execution tracking and `ServiceManager` status reporting in `tests/server/test_service_manager.py`
- [x] 3.2 Implement last-round tracking in `RepoWorker` and read-only status method in `ServiceManager` in `src/devops_cli/server/service.py` and messages in `src/devops_cli/lang/en/messages.py` and verify tests pass with `uv run pytest tests/server/test_service_manager.py`

## 4. Router AuthorizationToken, Form Parsing and Responder

- [x] 4.1 Add failing tests for `AuthorizationToken` verifier, form parsing, 415 rejection on JSON, and Mattermost slash command responder in `tests/server/test_mattermost_slash_command.py`
- [x] 4.2 Implement `AuthorizationToken` verifier, form payload parsing, and Mattermost provider with synchronous responder in `src/devops_cli/server/routes/webhooks.py` and `src/devops_cli/server/service.py`, increment counter metric, and verify with `uv run pytest tests/server/test_mattermost_slash_command.py`

## 5. Documentation, Sync and Integration Verification

- [x] 5.1 Update Roadmap Service section in `k8s/README.md` and regenerate documentation with `uv run devops docs generate --sync-readme`
- [x] 5.2 Verify entire test suite passes with `uv run devops ci`

## Workflow follow-up

- Archive the change with `uv run devops openspec archive 1395-mattermost-roadmap-slash-command`.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
