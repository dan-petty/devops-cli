# Design

## Decisions

- **Command under `devops gh`.** The issue names `devops github app-token` as an example. devops-cli has no `github` group; `devops gh` is the GitHub group. So the command is `devops gh app-token --app renovate --write <path>`. `--app` is a choice with one value today, so the next App adds one value and its settings.
- **One minting path.** `GitHubApp` gets `permissions` and `key_source`. `mint_installation_token(app)` takes an App, and without one it mints for the App that the process acts as, as before. The Renovate App reuses the 422 and 401 reasons of the Service App.
- **App ID or Client ID.** gidgethub puts `app_id` into the JWT's `iss` claim as given. GitHub takes the App ID or the Client ID there. So `renovate.github_app_id` is a positive integer or a non-empty string, and the command sends it as given. The name stays as the issue gives it.
- **Key through the credential chain.** The key resolves as every credential does: keyring, Vault, variable, and the config file never. On a workstation the keyring holds it. In the init container, Secret `devops/renovate` gives `DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY`.
- **Atomic file, mode 0600.** `write_text_file` makes a temporary file in the target directory with mode 0600, writes the token with no newline, and replaces the target. A reader never sees a part of the token or another mode. A refused exchange writes nothing, so an old file stays.
- **Expiry.** GitHub ends the token after 1 hour. The command prints when, and the help says to run it again before each run that uses it. The CronJob of #4905 runs it in an init container on each run, and its `activeDeadlineSeconds` (3000 s) is less than the token's life.
- **Dry run reads no credential.** A keyring read is an external request (#412), so the dry run reads only the two IDs. It fails, as the run does, when an ID is not set.
- **App name.** The owner named the App `dan-petty-renovate` (2026-11-16). `CONST_RENOVATE_GITHUB_APP_SLUG` holds it for the messages, and Fail-to-Pass Check skips `dan-petty-renovate[bot]`.

## Rejected alternatives

- **A new `devops github` group.** It would hold the same API as `devops gh` under a second name.
- **A setting named `renovate.github_app_client_id`.** The issue and #4893 owner step 3 name `renovate.github_app_id`, and GitHub takes both forms. One setting that takes either form keeps the owner steps as written.
- **An integer-only `renovate.github_app_id`.** It refuses the Client ID that GitHub now shows first on the App page.
- **A token file with a trailing newline.** A reader that does not trim would send the newline in the `Authorization` header. Renovate's `config.js` can read the file as is.
- **A `--print` option.** The token would reach the pod log. The issue forbids it.
