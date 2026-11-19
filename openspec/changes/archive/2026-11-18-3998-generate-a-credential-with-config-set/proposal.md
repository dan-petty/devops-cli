# Proposal

## Why

Today `devops config set` stores only a value that a person makes with a tool outside `devops`, and `devops k8s push-secrets` is the only command that makes a credential with the generator that the project declares, because it also writes the cluster. #3998 asks for one command that makes the value on the workstation alone and stores it in the OS keyring, from the generator that the project already declares.

## What Changes

- Add `generator_for_option(option)` and `generator_option_names()` to `src/devops_cli/k8s/cluster_secrets.py`, so one table answers the generator of a managed credential.
- Add the `--generate` flag, the `--rotate` flag and their refusal rules to the set command in `src/devops_cli/commands/config.py`, with the new messages in `src/devops_cli/lang/en/messages.py` and the new help text in `src/devops_cli/lang/en/help.py`.
- Add the tests of the new behavior to `tests/commands/test_config_commands.py` and the lookup test to `tests/k8s/test_cluster_secret_plan.py`.
- Change the prose of the set command in `generate_configuration_docs` of `src/devops_cli/docs/generator.py`, with its test in `tests/docs/test_docs.py`, because `docs/CONFIGURATION.md` is generated from that function and no hand edit of it survives.
- Edit the Crawl4AI bullet of `k8s/README.md`, then regenerate `docs/CONFIGURATION.md`, `docs/commands/config.md` and `docs/CLI_REFERENCE.md` with `uv run devops docs generate`.
- Record the new behavior as a spec delta of `config-commands`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: devops config set --generate stores a declared credential, The generator of a credential comes from the cluster Secret table, A credential with no declared generator is refused, A stored credential is kept unless the rotate flag is given, The rotate flag replaces the stored credential, The dry run of a generate writes nothing, The generate flag refuses a value and a file, The rotate flag needs the generate flag

## Impact

- Code: `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/commands/config.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/docs/generator.py`
- Documents: `k8s/README.md`, `docs/CONFIGURATION.md`, `docs/commands/config.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/k8s/test_cluster_secret_plan.py`, `tests/commands/test_config_commands.py`, `tests/docs/test_docs.py`

## Feasibility

- `search_code` for `generator_for_option` answered No match., so no code turns a managed credential option into its generator today, and that absence is the premise of #3998.
- `read_file` showed the command that the change extends: `src/devops_cli/commands/config.py:266:@app.command("set")` and `src/devops_cli/commands/config.py:268:def set_value(`, which take a VALUE, `--from-file` and `--dry-run` and no generate flag.
- The probe line confirms that the credential is an option and no path: The path `crawl4ai.api_token` is no file of the staging commit. No commit in the history deleted or renamed it.
- `read_file` showed the Crawl4AI row of the table: `src/devops_cli/k8s/cluster_secrets.py:347:generator=SecretGenerator("urlsafe", 32),` and `src/devops_cli/k8s/cluster_secrets.py:212:_CRAWL4AI_TOKEN = KeyringSource.for_credential("crawl4ai.api_token")`, so the project declares the encoding `urlsafe` and the byte count `32` of that token and ties the option to its keyring entry.
- `read_file` showed that the value comes from the standard library: `src/devops_cli/k8s/cluster_secrets.py:141:encode = secrets.token_hex if self.encoding == "hex" else secrets.token_urlsafe`.
- `read_file` showed that the push makes a value with the same generator: `src/devops_cli/k8s/secret_push.py:443:adopted, state, origin = entry.generator.generate(), EntryState.GENERATED, "generated"`.
- `read_file` showed that the push stores each value it made before it writes the cluster: `src/devops_cli/k8s/secret_push.py:556:keyring_write(key, value)`.
- `search_code` showed the plan entry that the new test calls: `src/devops_cli/k8s/secret_push.py:468:def plan_push(selected: Sequence[ClusterSecret], options: PushOptions) -> PushPlan:`.
- `search_code` and `read_file` showed the keyring calls that the command reuses: `src/devops_cli/config/os_keyring.py:298:def keyring_write(key: str, value: str) -> None` and `src/devops_cli/config/os_keyring.py:286:def keyring_read(key: str) -> str | None`.
- `read_file` showed that a dotted option names one credential record: `src/devops_cli/config/env.py:191:return _CREDENTIALS_BY_KEY[key]`, and that the credential keys are the secret fields: `src/devops_cli/config/settings.py:250:_SECRET_FIELDS: frozenset[str] = secret_keys()`.
- `read_file` showed the Crawl4AI bullet that the last group rewrites: `k8s/README.md:790:One keyring value`, which tells a person to run the push and says that no other command writes the token.
- `read_file` showed that the configuration page is generated: `docs/CONFIGURATION.md:3:This document is automatically generated from`, and showed the prose of the set command in its source: `src/devops_cli/docs/generator.py:800:takes a key that names a settings field with a value`, written at `src/devops_cli/docs/generator.py:1356:results["CONFIGURATION.md"] = self.generate_configuration_docs()`.
- `read_file` showed the module that already tests that function: `tests/docs/test_docs.py:530:content = generator.generate_configuration_docs()`, so group 3 writes its failing test there.
- `read_file` showed the message that a conflicting VALUE raises today: `src/devops_cli/lang/en/messages.py:389:from_file_and_value: str = "Give VALUE or --from-file, not both."`, so the new conflict messages sit beside it.
- `generate_configuration_docs` needs no checkout, a client or a network: it reads the settings model and the command tree in its own process.
- `keyring_write` needs a client of the OS keyring service and no network; `keyring_read` and `require_persistent_keyring` need the same client. The `keyring_store` fixture of `tests/commands/test_config_commands.py` replaces that client, so no test reaches the OS keyring service.
- `plan_push` needs a client of the cluster, because it reads the live Secrets and checks each namespace; the new test doubles it with `tests/support/cluster_secret_fakes.py:39:class FakeCluster:`, so no test reaches a cluster.
- The verify programs are `uv run devops ci test` and `uv run devops ci docs`, both from the runner image, which holds `uv` and `python`; no other tool is needed. The pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL` and `allowPrivilegeEscalation: false`. The live check needs `kubectl`, which is `NOT_IN_RUNNER`, and an unlocked OS keyring, so a person runs it on a workstation.
- The first checks are `uv run devops ci test tests/k8s/test_cluster_secret_plan.py`, `uv run devops ci test tests/commands/test_config_commands.py` and `uv run devops ci test tests/docs/test_docs.py`, and the live check on a workstation is `uv run devops k8s push-secrets --only devops/crawl4ai --plan` after the generate.
- The set of managed credential options whose row declares a generator is not counted by any tool of this run: the count is unverified, the verify of the first group `uv run devops ci test tests/k8s/test_cluster_secret_plan.py` is its census, and the step stops when the result differs from the plan. Each option whose row declares a generator is allowlisted because the row declares its encoding and its byte count; each option whose row declares none is restricted, and the command refuses it and names the options that have one.

## Existing Tool Considered

`keyring` (https://pypi.org/project/keyring, MIT, maintained, last activity 2025-11-16) writes and reads the OS keyring entry, and the standard library `secrets` module behind `SecretGenerator.generate` makes the random value. The change adopts both and builds no generator: it adds one lookup, one helper and two flags, with no new dependency.

## Dependencies

None.
