# Proposal: #4897

## Why

Issue #4897, child 2 of tracker #4893. Self-hosted Renovate runs as its own GitHub App, and it takes only an installation token. GitHub ends that token after 1 hour, and Renovate has no option for an App ID or a private key. No devops command writes an installation token to a file. The minting code in `src/devops_cli/github/app_installation.py` serves only the Service App. The owner named the App `dan-petty-renovate` on 2026-11-16, so its bot login is `dan-petty-renovate[bot]`, not the planned `devops-cli-renovate[bot]`.

## What Changes

- Add the settings `renovate.github_app_id` and `renovate.github_app_installation_id`, and the credential `renovate.github_app_private_key` (keyring entry `renovate_github_app_private_key`), in the form of the `argocd.github_app_*` settings. `renovate.github_app_id` takes the App ID or the App's Client ID, because GitHub takes either one as the issuer of the App's JWT.
- Add `devops gh app-token --app renovate --write <path>`. It mints the token through `mint_installation_token`, asks only for the 9 Renovate permissions, and writes the token to `<path>` with mode 0600 through an atomic replace. It prints the path and when GitHub ends the token, never the token.
- `--dry-run` sends no request and reads no credential. It shows the request, its body, and the token as a placeholder.
- A setting that is not set gives an error that names the setting and its variable.
- `GitHubApp` gets the permissions that its token asks for and the source of its key, so the Service App and the Renovate App share one minting path.
- Fail-to-Pass Check skips `dan-petty-renovate[bot]` in place of `devops-cli-renovate[bot]`.
- A command, its messages and a workflow condition change, so the change carries spec deltas.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `renovate-app-token`: How `devops gh app-token` writes an installation token of the Renovate App to a file.

### Modified Capabilities

- `ci-fail-to-pass`: The job skips the bot of the Renovate App by its new login.

## Impact

- `src/devops_cli/github/app_token.py`: new module with the command's logic.
- `src/devops_cli/github/app_installation.py`: `GitHubApp.permissions`, `GitHubApp.key_source`, `mint_installation_token(app)` and `installation_token_path`.
- `src/devops_cli/commands/gh.py`, `src/devops_cli/lang/en/`, `src/devops_cli/config/`: the command, its texts, settings and credential.
- `.github/workflows/fail-to-pass.yml`, `docs/SDLC.md`: the new bot login.
- `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/CLI_REFERENCE.md`, `docs/commands/gh.md`: generated.
- No cluster object changes. #4905 runs the command in the init container of the Renovate CronJob.

## Feasibility

- gidgethub 6.0.0 `gidgethub.apps.get_jwt` puts the `app_id` argument as given into the `iss` claim, and `GitHubAPI.post` sends the JWT as `Authorization: Bearer`. The existing `_exchange` already uses this path. A test decodes the JWT and reads `iss` for an App ID and a Client ID.
- GitHub's App settings page says: "Using your App ID to get installation tokens? You can now use your Client ID instead." (owner, 2026-11-16).
- `POST /app/installations/{installation_id}/access_tokens` takes a `permissions` body. The existing Service code already sends one (#2473).
- `output.file_writer.write_text_file` writes through a temporary file and `os.replace`, with the mode set before the content.

## Existing Tool Considered

gidgethub (Apache-2.0, maintained, in use) signs the JWT and exchanges it. The change reuses `mint_installation_token` and writes no JWT code. Rejected, as the issue records: `actions/create-github-app-token` (GitHub Actions only), the npm package `github-app-installation-token` (last release January 2022), the image `mshekow/github-app-installation-token` (no license), Link-/gh-token (no image, so a pod downloads a binary at run time), the External Secrets Operator `GithubAccessToken` generator (a new operator) and a JWT in the Renovate pod (home-grown crypto). Written cost: about 120 lines of code and 230 lines of tests, about 150k tokens and 1.5 hours. The change deletes no internal code: the Service App keeps its path.
