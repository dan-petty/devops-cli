# Tasks

## 1. No secret value as an MCP tool parameter

Kind: behavior. Reads: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/docker/cosign.py`, `src/devops_cli/commands/vault.py`, `src/devops_cli/ai/mcp/argument_contract.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/security/sanitizer.py`, `src/devops_cli/roadmap/agent_run.py`, `tests/ai/mcp/test_mcp_tool_secrets.py` (new), `tests/ai/client/test_roadmap_agent_run.py`, `tests/ai/mcp/test_fastmcp_contracts.py`, `tests/ai/mcp/test_docker_cosign.py`, `tests/ai/mcp/test_mcp.py`, `tests/ai/mcp/test_pydantic_ai_mcp.py`.

- [x] 1.1 Write failing tests in `tests/ai/mcp/test_mcp_tool_secrets.py` for the scenarios of "No MCP tool publishes a parameter that takes a secret value" and "The sign tool takes the OIDC token as a keyring reference only", and in `tests/ai/client/test_roadmap_agent_run.py` for "The run trace hides an argument by its name"
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp_tool_secrets.py tests/ai/client/test_roadmap_agent_run.py` fails on the base
- [x] 1.2 Add `CONST_MCP_SECRET_PARAMETER_WORDS`, `CONST_MCP_SECRET_PARAMETER_ALLOWLIST`, `is_secret_parameter_name` and `mask_secret_named_values`. Delete the `vault set` row of `CONST_MCP_EXPOSURE_TABLE`, restrict `vault get` to `path`, `key` and `dry_run`, replace the environment hand-off of the sign tool with the reference check, and mask the argument of `RunTrace` by name
  - Verification: `uv run devops ci test tests/ai/mcp tests/ai/client/test_roadmap_agent_run.py tests/roadmap`
- [x] 1.3 Move the tests that used `vault_set` as their secret-carrying tool to `valkey_set`, list `vault set` as excluded in `tests/ai/mcp/test_mcp.py`, and delete the test of the environment hand-off
  - Verification: `uv run devops ci test tests/ai/mcp`

## 2. Rule and documents

Kind: documents. Reads: `SECURITY.md`, `k8s/README.md`. Changes: `SECURITY.md`, `k8s/README.md`, `docs/MCP_TOOLS.md`.

- [x] 2.1 Add rule 12, **MCP Tool Secrets**, to `SECURITY.md`, renumber Hosted Models to 13, update the citation in `k8s/README.md`, and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme && uv run devops docs check`

## 3. Archive

Kind: other. Reads: `openspec/changes/3222-mcp-tool-secrets`. Changes: `openspec/specs/mcp-tool-secrets/spec.md`, `openspec/changes/archive`.

- [x] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 3222-mcp-tool-secrets`

## Workflow follow-up

- `valkey_set.value` and `sandbox_deploy.env` can carry a secret that a person gives. A name cannot find them, and the change does not close them. Issue #3230 decides them.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
