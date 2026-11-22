# Proposal: #6781

## Why
Closes #6781. The command `devops repos onboard` of #6773 seals the release key `RELEASE_APP_PRIVATE_KEY` into the GitHub Actions environment `release` of a repository (owner decision D2: never a repository-level secret). `devops gh secret sync` (`src/devops_cli/github/secrets.py`) writes only repository secrets: it reads the public key of `repos/{repo}/actions/secrets` and puts each sealed value there. It reads each value from the OS keyring or from Vault, by the name of the secret, and it cannot read a value from a file, such as the PEM file that `--release-key-file` of #6773 gives.

## What Changes
- `devops gh secret sync` gets the option `--env <name>`. With it, the command reads the public key of the environment (`GET repos/{repo}/environments/{env}/secrets/public-key`), seals each value with the same PyNaCl sealed box, and sends the body of `PUT repos/{repo}/environments/{env}/secrets/{name}` on stdin. The command encodes the environment name for the URL. Without `--env`, the command writes repository secrets as before.
- `devops gh secret sync` gets the option `--from-file <path>`. The file, or stdin when the path is `-`, gives the value of the one secret that `--secret-names` names. The command refuses `--from-file` with more than one secret name, and with `--source vault`. The reader is the reader of `devops config set --from-file`, moved to `src/devops_cli/config/secret_input.py`, so both commands keep one rule: at most 64 KiB, UTF-8 text, not empty, and every line as the input has it.
- `sync_repository_secrets` and `sync_secrets_requests` take `environment`, and `sync_repository_secrets` takes `value`, so #6773 calls the library and not the command.
- The dry run plans the environment routes and sends no request.
- No value goes to the output, a log record, a span or the text of an error. Tests assert it with a known test value.
- The secret group `devops gh secret` gets its own help text in the CLI reference.
- A devops command and its options change, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities
- `gh-secret-sync`: new capability. ADDED requirements for the scope of a secret, the source of a value, the dry run and the value that no output shows.

## Impact
- `devops gh secret sync` writes environment secrets. #6773 uses the library functions for its row 6.
- `devops config set --from-file` keeps its behavior and its messages: only the place of the reader changes.
- `docs/commands/gh.md` and `docs/CLI_REFERENCE.md` are generated again.
- No new dependency. PyNaCl is already a dependency.

## Feasibility
- GitHub REST documentation (https://docs.github.com/en/rest/actions/secrets, read 2026-11-22): "Get an environment public key" is `GET /repos/{owner}/{repo}/environments/{environment_name}/secrets/public-key`, and "Create or update an environment secret" is `PUT /repos/{owner}/{repo}/environments/{environment_name}/secrets/{secret_name}` with the required body parameters `encrypted_value` and `key_id`. The description of `environment_name` says: "The name must be URL encoded. For example, any slashes in the name must be replaced with %2F."
- Command output (read-only GET, 2026-11-22): `devops gh api repos/dan-petty/devops-cli/environments/release/secrets/public-key` returns a `key_id` and a 44-character base64 `key`, the same shape as the repository public key that `encrypt_secret` reads.
- Code: on origin/main `8e99f1da6`, `get_public_key_args`, `upload_secret_args` and `sync_secrets_requests` in `src/devops_cli/github/secrets.py` build only the paths under `repos/{repo}/actions/secrets`. `_secret_from_file` and `_read_to_end` in `src/devops_cli/commands/config.py` read a credential from a file or stdin.

## Existing Tool Considered
- `gh secret set --env <name>` of the GitHub CLI seals and puts an environment secret. The command does not use it: every `gh` call of devops-cli goes through `run_gh` and its rate limiter, the dry run of devops-cli plans each request as a `gh api` call, and `gh secret set` takes the value as an argument (`--body`, which the process list shows) or on stdin in its own form. The `gh api` path of this module already sends the sealed body on stdin.
- PyNaCl (Apache-2.0, maintained) seals the value: the module already uses its `SealedBox`. Python's `urllib.parse.quote` encodes the environment name.
- Build cost: about 60 lines of code and 12 tests; about 150k tokens and 1 hour to build, and a low cost to keep, because the change adds one path builder and reuses the seal, the upload and the reader.
- The change deletes `_read_to_end` and the read part of `_secret_from_file` in `src/devops_cli/commands/config.py`, which move to the shared reader.
