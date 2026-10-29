# Design

## Decisions

- **The MCP tool publishes no address.** `_PATH_PARAM_RESTRICTIONS` lets a command publish some of its options. `("vault", "status")` gets an entry with `dry_run` alone. A model has no address to give, so the defect has no input. A call that names `vault_addr` fails at the argument contract, before the command runs.
- **A list of allowed options, not a list of removed options.** This is the rule of the table. A new option of `devops vault status` stays unpublished until a person adds it.
- **The tool asks the configured Vault.** The command reads `VAULT_ADDR` and then `DEVOPS_CLI_VAULT_ADDR`, and the tool does the same. The settings model has no Vault key, so this change adds none. With no address set, the broker raises an error that names both variables. The tool gives that error to the caller and sends no request.
- **The command keeps `--addr`.** A person types it at the command line. No model sits between the person and the option, as in #2480, #2634 and #2635.
- **The broker refuses `?` and `#` in an address.** The model cannot give an address now, but a person can set one by mistake, and the request would then go to a path that the person did not mean. `vault_url` joins the path to the address as text. A query or a fragment in the address makes that text the query or the fragment. httpx2 sends the path before it, with no `/v1/sys/health`. The check is a test of two characters, because `urlsplit` reports an empty query or fragment for `http://h/p?` and `http://h/p#`, and both still change the path. The error does not repeat the address, as an address can hold user information.
- **The error for a missing address names the two variables.** The old text said "or pass --vault-addr". No such option exists. The `status` command has `--addr`, and the help of that command shows it.
- **The Vault client keeps the private level.** Vault is an internal service. The public level would refuse the usual address. With a fixed address, the level does not need to guard against a model.
- **The tests are in `tests/test_vault_cmd.py` and `tests/test_vault_broker.py`.** The first file tests the command and the tool already. The tool tests call the tool through a FastMCP `Client`, as the tests of #2635 do. They use `scripted_resolver` and `record_connects` from `tests/web_fakes.py` and read the bytes on the wire. The `vault` domain is withheld from the tool listing, so each test hydrates it first.

## Rejected alternatives

- **Keep the option and dial at the public level.** The `EgressLevel.PUBLIC` docstring names this level for a URL that a model gives. It stops the loopback and private scan. But the model could still make the tool send a GET request to any public host and path. It would also refuse the usual Vault address. The tool needs no address, because it reports the configured Vault.
- **Check the path or the host of the address that the model gives.** A host list or a path check is a second rule on an input that the fix removes. The defect is that a model gives an address at all. AGENTS.md rule 2 warns about a fix on a fix.
- **Strip the query or fragment of the address.** A person who set a bad address would get no error and could not see the cause. A refusal says what is wrong.
- **Test `urlsplit(addr).query` only.** This misses the fragment, which changes the path in the same way. The probe in the proposal shows it.
- **An invariant test that no MCP tool publishes a URL option.** Another tool may still publish one. An invariant needs an allow list of such tools, and an allow list is an escape. Each fix removes its own tool.
