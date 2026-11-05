# Proposal

## Why

`devops config audit-keys` does not find a plaintext secret under a key with more than two levels. The scanner `_scan_yaml_for_secret_keys` examines only `<section>.<option>`. The managed credential `service.github_app.private_key` has three levels. So the audit reports a config file compliant while the file holds a plaintext private key. The help of the command says that it exits 1 for a plaintext secret, and that is false for this key. See #2511.

## What Changes

- The scanner walks the parsed YAML at any depth. It builds the dotted key of each entry and reports each entry whose dotted key is a managed credential (`secret_keys()`) and that holds a value.
- A leak names `<path>:<dotted key>`.
- The change fits one pull request.
- The change alters the report of a devops command, so it carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: the audit finds a plaintext secret at any depth (an ADDED requirement). The format of a leak changes from `<path>:<section>.<key>` to `<path>:<dotted key>` (a MODIFIED requirement).

## Impact

- Code: `src/devops_cli/commands/config.py`
- Tests: `tests/commands/test_config_audit_keys.py`

## Feasibility

I wrote a config file with `service.github_app.private_key` set to a fake value, and ran `devops config audit-keys --json` on the base. The report showed `is_compliant: true` and `plaintext_leaks: []`, with exit code 0. The test `test_config_audit_keys_finds_a_plaintext_secret_at_its_full_dotted_key` records this run, and fails on the base. `secret_keys()` in `src/devops_cli/config/env.py` returns `service.github_app.private_key` (line 114), so the registry already names the key. The premise holds.

## Existing Tool Considered

The issue lists Yelp/detect-secrets. It finds secrets by content heuristics. It has no knowledge of the `secret_keys()` registry, and it produces none of the fields of the report (`plaintext_leaks`, `is_compliant`, `unaudited_config_files`). The audit must decide by the dotted key, so a heuristic scanner does not cover the need. The change keeps the existing scanner and replaces its fixed two-level loop with a walk of the parsed YAML. The walk is one short function and uses PyYAML for the parse and `is_secret_field` for the match. The change deletes the two-level loop.
