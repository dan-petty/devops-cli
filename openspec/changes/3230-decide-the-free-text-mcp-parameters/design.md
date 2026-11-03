# Design

## Decisions

- **A path restriction takes a `denied` set, and the generator omits each parameter that it names.**: It removes `env` from `sandbox_deploy` and keeps every other option of the command published, so the tool keeps its useful work.
- **The `valkey_set` tool leaves the exposure table and the restriction table.**: Its `value` argument is the cache value itself and the command resolves no reference from the secret store, so the tool cannot publish it and stay within rule 12.
- **Tests referencing `valkey_set` update to `tf_apply` or add exclusion entries.**: `test_export_schemas_command` in `tests/ai/mcp/test_mcp.py` tests `tf_apply.json`. Contract tests in `tests/ai/mcp/test_fastmcp_contracts.py` test `tf_apply`. `mcp_command_exclusions` records `("valkey", "set")` so command coverage tests pass.
- **The free-text guard fails on the exact names `env`, `values`, `value` and `data`, with an allow-list that carries a reason.**: It mirrors the guard of #3222, so one pattern covers both guards, and it avoids the false positives of a substring match on names such as `field_value`.
- **`k8s_diff_helm.values` is allow-listed with an explicit reason.**: The parameter takes paths to local YAML files to override Helm values, not arbitrary secret payloads.
- **The guard also fails on an allow-list entry that matches no published parameter.**: A stale entry would otherwise allow a name that a later tool publishes for no reason.
- **The guard reads the published JSON schema of the generated tools.**: The schema is what a model sees, so the test asserts the published contract and no internal structure.

## Rejected alternatives

- **A full `allowed` list on the `sandbox_deploy` restriction in place of a `denied` set.**: The command publishes many options, so the list would need every one of them and would drop an option that the command adds later.
- **Remove the `sandbox_deploy` tool entirely.**: The tool publishes no other secret parameter, and SECURITY.md rule 11 accepts its `workspace` option through `_check_sandbox_preconditions` in `src/devops_cli/ai/mcp/generator.py`.
- **Accept only a `keyring:` reference in `valkey_set.value`, as `docker_sign` does for its `oidc_token`.**: `_check_oidc_token_reference` in `src/devops_cli/ai/mcp/generator.py` refuses a token that is no `keyring:` reference, but the `valkey set` command resolves no such reference, and a secret in argv would be exposed.
- **Allow `valkey_set.value` with a reason in the allow-list.**: A model writes the argument, so the value passes through the model context, the provider and the run trace, which SECURITY.md rule 12 forbids.
- **A substring scan of every published parameter name.**: `CONST_MCP_SECRET_PARAMETER_WORDS` matches substrings, and names such as `field_value` would then fail with no sink reason.
