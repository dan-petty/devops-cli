# Design

## Decisions

- **The guard reads the published schema, not the Click commands.** The schema is what a model sees. A hand-written tool, such as `security_intel_package`, has no Click command, and the sweep covers it too.
- **A name word list, and a type filter.** The issue lists the words. The list adds `passphrase` and `key_values`. A match counts only when the parameter can hold text (a string, or a list of strings), because a flag, a number and a fixed choice cannot hold a secret value. That leaves `max_tokens` (an integer) and `push_secrets` (a boolean) out without an allow-list entry.
- **The allow-list is `CONST_MCP_SECRET_PARAMETER_ALLOWLIST`, a constant in `constants.py` and not a column of the exposure table.** A table row is a command, and the entry is a parameter of a tool. Hand-written tools are not in the table. The key is `(tool, parameter)` and the value is the reason.
- **Three entries, each with a reason.** `docker_sign.oidc_token` takes only a `keyring:<name>` reference, and the generator refuses any other value. `k8s_create_tls_secret.secret_name` and `k8s_enable_tls.secret_name` name a Kubernetes Secret object. The test checks that every entry matches a live parameter, so a renamed or removed parameter does not leave a dead entry.
- **`vault_set` leaves the tool surface.** The tool exists to carry secret values from the model to Vault. The rule forbids it. A person keeps `devops vault set`.
- **`vault_get` loses `show`.** The rule says that a tool never returns a credential. The option is cut with `_PATH_PARAM_RESTRICTIONS`, as for other options that are for a person.
- **`docker_sign` keeps `oidc_token` as a reference.** The owner's decision on #3219 names an opaque reference that the server resolves from the secret store. `keyring:<name>` is that, and the command resolves it already. The check is a `ValidationError` in the tool function, as `_check_model_endpoints` does for the benchmark. Its message names the parameter and never the value.
- **The run trace masks by name first.** `mask_secret_named_values` replaces the value under a secret-suggesting key at any depth of dicts and lists, and `bounded_text` then masks by form. The name matcher is shared with the guard test, in `sanitizer.py`, next to the other masking code.
- **No new log code.** `ArgumentValueLogFilter` replaces whole argument mappings in the FastMCP log, which is stronger than a mask by name. The rule cites it.

## Rejected alternatives

- **Put `vault_set.key_values` on the allow-list.** It is a secret value by purpose. An entry for it would make the rule empty.
- **Give `vault_set` a `credential_ref` for each value.** The command stores a value that a person gives. A reference would need a new source of values and no consumer asks for it.
- **Drop `oidc_token` from the sign tool.** Keyless signing outside a CI job with ambient identity needs a token, and the reference form is the carrier that the owner named.
- **Refuse in `generate_mcp_tools` at start-up instead of in a test.** The server would fail to start for a developer's new option, and the hand-written tools would still need the test. A test fails in CI where the change is reviewed.
- **Match the whole word only.** `secret_name` and `oidc_token` need a substring match, and the allow-list with reasons is the place to excuse the safe ones.
