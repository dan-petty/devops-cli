# Proposal

## Why

Issue #3222. The model writes the arguments of an MCP tool call. A secret in an argument passes through the model context, the provider, the LLM cache and the run trace, and the model can be induced to send it to another tool. `SECURITY.md` rule 11 treats a URL or a host that a model gives to a tool as untrusted. No rule covers a credential. Jobs reach the MCP server through LiteLLM (#3219), and the owner decided that the harness sets the credential of an execution, so the permissions are in the credential and not in the tool.

A sweep of the 146 published tool schemas shows that the rule is broken today:

- `vault_set` takes `key_values`, the `KEY=VALUE` secrets to store. The whole purpose of the tool is a secret value in an argument.
- `docker_sign` takes `oidc_token`, an identity token. The generator moved a raw token into the environment of the command, but the token was still an argument that the model wrote.
- `vault_get` takes `show`, which prints the secret in plain text into the reply.

Three more parameters have a secret word in the name and hold no secret: `secret_name` of `k8s_create_tls_secret` and of `k8s_enable_tls` names a Kubernetes Secret object.

## What Changes

- `SECURITY.md` has a new rule 12, **MCP Tool Secrets**, after rule 11, and a section of the same name that holds the detail. The rule is short because the section of principles has little room under the token cap of an implement step (2953 of 3000 tokens before the change). The old rule 12 (Hosted Models) is rule 13, and `k8s/README.md` cites it by that number.
- The implement step gives the `MCP Tool Secrets` section to a group that changes a file under `src/devops_cli/ai/mcp/` (a route in `src/devops_cli/roadmap/step_rules.py`).
- A guard test, `tests/ai/mcp/test_mcp_tool_secrets.py`, reads the published schema of every registered tool. It fails on a text parameter whose name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS`, unless `CONST_MCP_SECRET_PARAMETER_ALLOWLIST` names the tool and the parameter with a reason. It also fails on an entry that matches no parameter, and on a reason of less than 30 characters. Both constants are in `src/devops_cli/config/constants.py`, apart from the exposure table.
- `vault_set` is no tool. A person runs `devops vault set` at the shell. Its entry leaves `CONST_MCP_EXPOSURE_TABLE`.
- `vault_get` publishes `path`, `key` and `dry_run`, and no `show`.
- `docker_sign` takes `oidc_token` only as `keyring:<name>`. The tool refuses a token that is not a reference, before any command runs, and the error does not repeat the token. The raw-token hand-off through the environment (`_extract_extra_env`, `_should_skip_option`) is deleted.
- `RunTrace` hides the value of a tool-call argument by the name of the argument (`mask_secret_named_values` in `src/devops_cli/security/sanitizer.py`), and `mask_secrets` stays the second guard on the rest.
- The log of FastMCP needs no change: `ArgumentValueLogFilter` already replaces every argument mapping of a call. The rule names it.
- A consumer sees the tool schemas and the message of the step, so the change carries a spec delta that creates the capability `mcp-tool-secrets` and one scenario for `roadmap-implement-step`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `mcp-tool-secrets`: which parameters an MCP tool publishes with respect to secret values, how `docker_sign` takes its OIDC token, and what the run trace shows of a tool-call argument.

### Modified Capabilities

- `roadmap-implement-step`: the requirement "The routes name the documents of a group" gains a scenario for a group that changes an MCP tool.

## Impact

- `SECURITY.md` and `k8s/README.md` (the number of the Hosted Models rule).
- `src/devops_cli/config/constants.py`: two constants added, one table entry deleted.
- `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/lang/en/errors.py`, `src/devops_cli/security/sanitizer.py`, `src/devops_cli/roadmap/agent_run.py` and `src/devops_cli/roadmap/step_rules.py`.
- `tests/ai/mcp/test_mcp_tool_secrets.py` (new), and the tests of `vault_set` and of the `docker_sign` hand-off in `tests/ai/mcp/` and `tests/ai/client/test_roadmap_agent_run.py`.
- `docs/MCP_TOOLS.md` (generated).

## Feasibility

- The schemas are reachable offline. `asyncio.run(mcp._list_tools())` on `devops_cli.ai.mcp.server.mcp` returns every registered tool with its JSON Schema, and the existing tests of `tests/ai/mcp/test_fastmcp_contracts.py` use it. No cluster and no network are needed.
- On `origin/main` at `d312a98c`, the sweep over 146 tools gave four hits for the issue's words plus `key_values`: `docker_sign.oidc_token`, `k8s_create_tls_secret.secret_name`, `k8s_enable_tls.secret_name` and `vault_set.key_values`. The words alone find three of them: `key_values` has no secret word, so it is a word of its own in the list. `ai_pack_context.max_tokens` (an integer) and `k8s_deploy_stack.push_secrets` (a boolean) match a word too, and the guard skips a parameter that cannot hold text.
- `vault set` stores the values that its arguments carry (`src/devops_cli/commands/vault.py`, `broker.set_secret(path, payload)`), so no reference can replace them without a new command. `docker sign` resolves `keyring:<name>` itself (`_resolve_oidc_env` in `src/devops_cli/docker/cosign.py`), so the reference form exists.
- `vault get` prints `***REDACTED***` unless `--show` is set (`_render_secret`), so the tool without `show` still answers whether the secret exists.
- Logging: `ArgumentValueLogFilter` (`src/devops_cli/ai/mcp/argument_contract.py`) replaces each mapping argument of the FastMCP operations logger, and tests in `test_fastmcp_contracts.py` hold it. The run trace is built in `RunTrace._add_reply` (`src/devops_cli/roadmap/agent_run.py`). It masked the argument text by form only, which hides a token of a known shape and not an opaque value under `api_key`.
- No header or `credential_ref` exists yet: the harness client is #3221 and waits for #3207. The rule states them as the carriers, and the code adds none.
- Not covered by a name: `valkey_set.value` (cache data) and `sandbox_deploy.env` (`KEY=VALUE` pairs for a sandbox) can hold a secret that a person gives. A word list cannot find them, and they are left as they are.

## Existing Tool Considered

No open tool checks MCP tool schemas for secret parameters. The scanners the project runs (`gitleaks`, `bandit`) read code and files, not the parameters of a published schema. The change adds a test over `FastMCP.list_tools` and one name matcher that the test and the run trace share. Cost to build: about 60k tokens and 3 hours. Cost to keep: the two constants. A new allow-list entry needs a reason, and the test fails on a stale entry, so the list cannot grow quietly. Cost to fix a tool that fails: one entry in `_PATH_PARAM_RESTRICTIONS`, or one table entry deleted.

The change deletes `_extract_extra_env` and `_should_skip_option` of `generator.py`, the `env=` hand-off of the sign tool and its test, and the `vault_set` row of `CONST_MCP_EXPOSURE_TABLE`.
