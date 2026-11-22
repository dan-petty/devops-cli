# Tasks

## 1. Secret sync seals a secret into an environment

Kind: behavior. Reads: `src/devops_cli/github/secrets.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/commands/config.py`, `tests/support/fakes/process.py`, `tests/support/fakes/otlp.py`. Changes: `src/devops_cli/github/secrets.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/commands/config.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/secret_input.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/github/test_github_secrets.py`.
Adds: `secrets_path`, `read_secret_input`

- [x] 1.1 Write the failing tests in `tests/github/test_github_secrets.py` for the scenarios of `gh-secret-sync`, with a fake of the Actions secrets routes on `process_fake` that holds one key pair for each scope, answers 404 for an unknown environment and opens each sealed PUT body: the environment routes, the URL-encoded name, the unknown environment, the value from a file with its last newline, the two refusals of `--from-file`, the dry run, and the known value `known-test-value-6781` in no output, `gh` argument or stdin, log record (`caplog`) or OTLP export (`otlp`)
  - Verification: `$ uv run devops ci test tests/github/test_github_secrets.py` fails on the base
- [x] 1.2 Move `_read_to_end` and the read checks of `_secret_from_file` from `src/devops_cli/commands/config.py` to `read_secret_input` in `src/devops_cli/config/secret_input.py`, and make `_secret_from_file` call it
  - Verification: `$ uv run devops ci test tests/commands/test_config.py tests/commands/test_config_commands.py` passes
- [x] 1.3 Add `secrets_path` and the `environment` parameter to the path builders, `get_repository_public_key`, `sync_secrets_requests` and `sync_repository_secrets`, and the `value` parameter to `sync_repository_secrets`, in `src/devops_cli/github/secrets.py`. Add `--env` and `--from-file` to `devops gh secret sync` in `src/devops_cli/commands/gh.py`, with their help texts and refusals, and give the group `devops gh secret` its help text
  - Verification: `$ uv run devops ci test tests/github/test_github_secrets.py tests/github/test_gh_api_status_branch_protection_secrets_dry_run.py` passes

## 2. Documents

Kind: other. Reads: `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`. Changes: `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`.

- [x] 2.1 Generate the command documentation again with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
