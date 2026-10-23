# Task: Agent Session Prerequisites — Gateway URL, 401 Hint, Deny Rules, and Read-Only Kubernetes Identity (#1154)

**Issue**: [#1154](https://github.com/dan-petty/devops-cli/issues/1154)
**Scope**: scope/agent
**Feasibility**: Verified against configuration settings model, environment variable mapping in `devops_cli.config.env`, `credentials_error` in `devops_cli.ai.client.models`, Claude Code permissions in `.claude/settings.json`, and Kubernetes manifests in `k8s/agents/` validated with `devops_cli.k8s.rbac.audit_rbac` and `kubectl kustomize`.

## Description

Agent sessions require secure configuration, isolated credentials, and read-only cluster access. This deliverable completes #1154:
- Declares `AI_GATEWAY_URL = "ai.gateway_url"` in `devops_cli.config.options`, mapped to environment variable `DEVOPS_CLI_AI_GATEWAY_URL` in `devops_cli.config.env` with an `EnvVarSpec` entry and documentation in `docs/ENV_VARS.md` and `docs/CONFIGURATION.md`.
- Declares environment-only constant `ENV_AGENT_GRANT = "DEVOPS_CLI_AGENT_GRANT"`.
- Updates `credentials_error` in `devops_cli.ai.client.models` to produce a grant-aware error hint when `DEVOPS_CLI_AGENT_GRANT` is present: naming the grant ID (truncated to 256 characters if excessive), indicating the grant expired or was revoked and that a person issues a new grant, and suppressing the generic `DEVOPS_CLI_AI_API_KEY` hint.
- Adds Claude Code deny rules in `.claude/settings.json` for `Read(//**/.claude/settings.local.json)`, `Read(~/.claude/settings.json)`, and `Read(~/.kube/**)`.
- Defines read-only agent identity under GitOps: ServiceAccount `devops-agent` in namespace `agents` with `automountServiceAccountToken: false`, bound via ClusterRoleBinding `devops-agent-view` to the built-in `view` ClusterRole.
- Configures namespace `agents` in `k8s/namespaces.yaml` enforcing `restricted` Pod Security Standards with sync-options `Prune=false,Delete=false`.
- Adds Argo CD Application `agents` in `k8s/argocd/apps/agents.yaml` under project `homelab`, admits destination namespace `agents`, and configures orphan-resource ignore rules for transient session secrets (`agent-grant-*`).
- Integrates agent manifests into `devops k8s deploy-stack --stack devops` (and `--stack all`) via `_MANIFESTS_BY_STACK["devops"]`.

## Acceptance Criteria

- [x] `DEVOPS_CLI_AI_GATEWAY_URL` sets `ai.gateway_url`, the env spec lists it as not secret, and `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` reflect it.
- [x] With `DEVOPS_CLI_AGENT_GRANT` set, a gateway 401 names the grant ID and says a person issues a new grant; without it, the hint is unchanged. Long grant IDs are capped at 256 characters.
- [x] `.claude/settings.json` denies `Read(//**/.claude/settings.local.json)`, `Read(~/.claude/settings.json)`, and `Read(~/.kube/**)`.
- [x] Unit and integration tests verify environment overrides, grant 401 hints, and settings file deny rules.
- Removed on 2026-10-22 by the person: the three `Read` deny rules and the test module that pinned them. The person wants agents to read the project folder and the kubeconfig. See the pull request that deletes `tests/test_claude_code_settings.py`.
- [x] `uv run devops docs check` passes with all generated documentation up to date.
- [x] `k8s/agents/` holds ServiceAccount `devops-agent` (automount off) and ClusterRoleBinding `devops-agent-view` to the built-in `view`.
- [x] Namespace `agents` is `restricted` and carries `Prune=false,Delete=false`.
- [x] Argo CD Application `agents` syncs `k8s/agents`, the `homelab` project admits the `agents` destination, and `agent-grant-*` Secrets are ignored orphans.
- [x] `devops k8s deploy-stack --stack devops` (and `--stack all`) applies both manifests on a cluster without Argo CD, and the dry run lists them.
- Pending a person: after Argo CD syncs the merge (or after `uv run devops k8s deploy-stack --stack devops` on a cluster without Argo CD), these print `no`: `kubectl auth can-i get secrets -A --as=system:serviceaccount:agents:devops-agent`, `kubectl auth can-i create pods/exec -n llm --as=system:serviceaccount:agents:devops-agent` and `kubectl auth can-i create jobs -n devops --as=system:serviceaccount:agents:devops-agent`. And `kubectl auth can-i list pods -A --as=system:serviceaccount:agents:devops-agent` prints `yes`.

## Deliverables

- [x] Added `AI_GATEWAY_URL` in `src/devops_cli/config/options.py`.
- [x] Added `ENV_AI_GATEWAY_URL` and `ENV_AGENT_GRANT` in `src/devops_cli/config/env.py`, mapped `AI_GATEWAY_URL` in `OPTION_TO_ENV_VAR`, and registered its `EnvVarSpec`.
- [x] Exported `AI_GATEWAY_URL`, `ENV_AI_GATEWAY_URL`, and `ENV_AGENT_GRANT` in `src/devops_cli/config/__init__.py`.
- [x] Updated `credentials_error` in `src/devops_cli/ai/client/models.py` with grant-aware 401 error message when `DEVOPS_CLI_AGENT_GRANT` is set.
- [x] Added `permissions.deny` rules in `.claude/settings.json`.
- [x] Added unit tests in `tests/test_claude_code_settings.py`, `tests/test_config_env_overrides.py`, and `tests/test_ai_gateway.py`.
- [x] Regenerated `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` via `devops docs generate`.
- [x] Created `k8s/agents/serviceaccount.yaml`, `k8s/agents/clusterrolebinding.yaml`, and `k8s/agents/kustomization.yaml`.
- [x] Added namespace `agents` in `k8s/namespaces.yaml` with `restricted` Pod Security Standards and `Prune=false,Delete=false`.
- [x] Created Argo CD Application `k8s/argocd/apps/agents.yaml`.
- [x] Added destination `agents` and orphan ignore `agent-grant-*` to `homelab` project in `k8s/argocd/apps/projects.yaml`.
- [x] Added agents manifests to `_MANIFESTS_BY_STACK["devops"]` in `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- [x] Updated `k8s/README.md` with leaf application count 23, directory structure, and `### Agent sessions` documentation.
- [x] Added comprehensive tests in `tests/test_k8s_agents_manifests.py` and updated `tests/test_k8s_argocd_apps.py`.
- [x] Added changelog fragment in `changelog.d/1154.md`.
