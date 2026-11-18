# Design

## Decisions

- **Add `generator_for_option(option)` and `generator_option_names()` to the cluster Secret table, beside `keyring_sources`.**: The table is the one declaration of each generator, and a row already ties a managed credential to its keyring entry, so the command and the push read one declaration per credential.
- **Take the managed credential option, such as `crawl4ai.api_token`, as the name that the generate flag takes.**: It is the name that the set command takes today, and the keyring source of a row holds it; a keyring-only key has no option name.
- **Exit non-zero and name the rotate flag when the keyring already holds a value.**: The push refuses a differing live value without a rotate flag in the same way, and a silent replacement breaks a client that holds the old token.
- **Make the value in the command's own process and store it with `keyring_write`, as the store step of the push does.**: No argument, prompt pipe or child process carries the value, so it reaches no shell history and no process list.
- **Make the dry run read nothing and print the encoding, the byte count and a masked placeholder.**: The dry run of the push makes no request in the same way, and a keyring read would make the result depend on the keyring state and on an unlocked keyring.
- **Refuse a VALUE or `--from-file` with the generate flag, and the rotate flag alone, as usage errors that exit 2, with the new messages beside the file and value message of `src/devops_cli/lang/en/messages.py`.**: Each of those runs names two sources of one value, so it has no single answer, and exit 2 is the class of a bad invocation that the file input already uses.
- **Put the lookup test with the tests of the cluster Secret table and the command tests with the other config command tests.**: Those modules hold the fake keyring and the table fixtures, so the tests reach no keyring service, no cluster and no network.
- **Change the prose of the set command in `generate_configuration_docs` of `src/devops_cli/docs/generator.py`, and regenerate the pages with `uv run devops docs generate`.**: `docs/CONFIGURATION.md` is a generated document whose source is that function, so a hand edit is overwritten and the `docs` row refuses the page; the generator is the only place where its prose changes.
- **Write the failing test of the page text in `tests/docs/test_docs.py`, which already builds the generator.**: That module holds the tests of `generate_configuration_docs`, so the test needs no new fixture and reaches no network.

## Rejected alternatives

- **A second generator table in the config command.**: `src/devops_cli/k8s/cluster_secrets.py:347:generator=SecretGenerator("urlsafe", 32),` is the one declaration of the Crawl4AI token, and a second table would drift from the push that reads it.
- **Call `plan_push` with a fake cluster to obtain the generator.**: `src/devops_cli/k8s/secret_push.py:443:adopted, state, origin = entry.generator.generate(), EntryState.GENERATED, "generated"` shows that the push reads the generator of the row, and `plan_push` reads the live Secrets, so the command would need a cluster for a value that the table already gives.
- **Name the keyring key, such as `crawl4ai_api_token`, in the generate flag.**: `k8s/README.md:790:One keyring value` names the keyring entry, and the set command names dotted options everywhere else, so a person would have to know the keyring name.
- **Name the Secret ref and key, such as the Crawl4AI Secret and its token key.**: `k8s/README.md:790:One keyring value` shows one keyring value feeding Secret `devops/crawl4ai` and a key of Secret `devops/devops-cli`, so a Secret ref names no single credential.
- **Replace the stored value and warn.**: A cluster client that holds the old token fails at its next call, and the push already refuses that replacement without the rotate flag.
- **Run `openssl rand` and read its standard output.**: It adds a child process, it knows no per-credential encoding or length, and the value would pass through a pipe that the shell can log.
- **Read the keyring in the dry run, to report whether it would replace.**: `src/devops_cli/commands/config.py:293:if dry_run or is_dry_run():` shows that the dry run of the set command writes nothing, and a keyring read would make the dry run depend on the keyring state.
- **Accept a keyring-only key, such as `searxng_secret_key`, in the generate flag.**: `src/devops_cli/k8s/cluster_secrets.py:697:def keyring_only_keys(table: Iterable[ClusterSecret] = CLUSTER_SECRETS) -> frozenset[str]:` shows that the table holds keys that no Settings option reads, so the set command has no option name for them today.
- **Edit `docs/CONFIGURATION.md` by hand to name the two commands.**: `src/devops_cli/docs/generator.py:730:This document is automatically generated from` is the source of that page, so a hand edit is overwritten and the `docs` row of the gate fails.
- **Adopt the `keyring` library as the whole answer to the issue.**: The alternatives check of 2026-11-09 gives it `partly`: the library writes the OS keyring entry and the standard library makes the value, but it holds no per-credential encoding or length and no link to the cluster Secret table.

## Security

The value crosses one trust boundary: the memory of the command process to one entry of the OS keyring. The value never reaches an argument, a file, a log record, the output or the shell history, and the command starts no child process. A person must confirm that the keyring stays unlocked for the run and that no wrapper passes a VALUE or a file together with the generate flag, and must confirm that the Crawl4AI bullet of the k8s README still tells the reader that only the push writes the cluster Secrets. If the rule breaks, the behavior test of the generate fails: it asserts that the output holds no part of the stored value, and the dry-run test asserts that the keyring content does not change.
