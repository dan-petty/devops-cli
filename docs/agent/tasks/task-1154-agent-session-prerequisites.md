# Task: Agent Session Prerequisites — Gateway URL, 401 Hint, and Deny Rules (#1154)

**Issue**: [#1154](https://github.com/dan-petty/devops-cli/issues/1154)
**Scope**: scope/agent
**Feasibility**: Verified against configuration settings model, environment variable mapping in `devops_cli.config.env`, `credentials_error` in `devops_cli.ai.client.models`, and Claude Code permissions in `.claude/settings.json`.

## Description

Agent sessions require secure configuration and isolated credentials. This task delivers slice (a) of #1154 as Part 1 of 2:
- Declares `AI_GATEWAY_URL = "ai.gateway_url"` in `devops_cli.config.options`, mapped to environment variable `DEVOPS_CLI_AI_GATEWAY_URL` in `devops_cli.config.env` with an `EnvVarSpec` entry and documentation in `docs/ENV_VARS.md` and `docs/CONFIGURATION.md`.
- Declares environment-only constant `ENV_AGENT_GRANT = "DEVOPS_CLI_AGENT_GRANT"`.
- Updates `credentials_error` in `devops_cli.ai.client.models` to produce a grant-aware error hint when `DEVOPS_CLI_AGENT_GRANT` is present: naming the grant ID (truncated to 256 characters if excessive), indicating the grant expired or was revoked and that a person issues a new grant, and suppressing the generic `DEVOPS_CLI_AI_API_KEY` hint.
- Adds Claude Code deny rules in `.claude/settings.json` for `Read(//**/.claude/settings.local.json)`, `Read(~/.claude/settings.json)`, and `Read(~/.kube/**)`.

Slice (b) delivering the read-only agent Kubernetes identity and manifests under `k8s/agents/` follows in PR 2 of #1154.

## Acceptance Criteria

- [x] `DEVOPS_CLI_AI_GATEWAY_URL` sets `ai.gateway_url`, the env spec lists it as not secret, and `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` reflect it.
- [x] With `DEVOPS_CLI_AGENT_GRANT` set, a gateway 401 names the grant ID and says a person issues a new grant; without it, the hint is unchanged. Long grant IDs are capped at 256 characters.
- [x] `.claude/settings.json` denies `Read(//**/.claude/settings.local.json)`, `Read(~/.claude/settings.json)`, and `Read(~/.kube/**)`.
- [x] Unit and integration tests verify environment overrides, grant 401 hints, and settings file deny rules.
- [x] `uv run devops docs check` passes with all generated documentation up to date.
- Follow-up in PR 2: `k8s/agents/` holds ServiceAccount `devops-agent` (automount off) and ClusterRoleBinding `devops-agent-view` to the built-in `view`.
- Follow-up in PR 2: Namespace `agents` is `restricted` and carries `Prune=false,Delete=false`.
- Follow-up in PR 2: Argo CD Application `agents` syncs `k8s/agents`, the `homelab` project admits the `agents` destination, and `agent-grant-*` Secrets are ignored orphans.
- Follow-up in PR 2: `devops k8s deploy-stack --stack devops` (and `--stack all`) applies both manifests on a cluster without Argo CD, and the dry run lists them.
- Pending a person: after Argo CD syncs the merge (or after `uv run devops k8s deploy-stack --stack devops` on a cluster without Argo CD), these print `no`: `kubectl auth can-i get secrets -A --as=system:serviceaccount:agents:devops-agent`, `kubectl auth can-i create pods/exec -n llm --as=system:serviceaccount:agents:devops-agent` and `kubectl auth can-i create jobs -n devops --as=system:serviceaccount:agents:devops-agent`. And `kubectl auth can-i list pods -A --as=system:serviceaccount:agents:devops-agent` prints `yes`.

## Deliverables

- [x] Added `AI_GATEWAY_URL` in `src/devops_cli/config/options.py`.
- [x] Added `ENV_AI_GATEWAY_URL` and `ENV_AGENT_GRANT` in `src/devops_cli/config/env.py`, mapped `AI_GATEWAY_URL` in `OPTION_TO_ENV_VAR`, and registered its `EnvVarSpec`.
- [x] Exported `AI_GATEWAY_URL`, `ENV_AI_GATEWAY_URL`, and `ENV_AGENT_GRANT` in `src/devops_cli/config/__init__.py`.
- [x] Updated `credentials_error` in `src/devops_cli/ai/client/models.py` with grant-aware 401 error message when `DEVOPS_CLI_AGENT_GRANT` is set.
- [x] Added `permissions.deny` rules in `.claude/settings.json`.
- [x] Added unit tests in `tests/test_claude_code_settings.py`, `tests/test_config_env_overrides.py`, and `tests/test_ai_gateway.py`.
- [x] Regenerated `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` via `devops docs generate`.
- Follow-up in PR 2: Add `k8s/agents/` manifests, `k8s/argocd/apps/agents.yaml`, and `stack_lifecycle.py` integration with `tests/test_k8s_agents_manifests.py`.
