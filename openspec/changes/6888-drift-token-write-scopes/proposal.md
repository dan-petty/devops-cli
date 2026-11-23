# Proposal: #6888

## Why
Closes #6888. The nightly drift Job (CronJob `repos-drift`, #6783) mints an App token that asks for read permissions only (`CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS`, setting `service.github_app.read_only`). GitHub gives the merge settings of a repository only to a token with Contents write, and the bypass actors of a ruleset only to a token with write access to the ruleset. Since #6875, rows 2 and 10 are `not readable` for these keys in each repository each night, so `RepositorySettingsUnreadable` fires and the check does not compare them. The owner decided on 2026-11-23 (#6875, comment 7104241763) that the token of the drift Job also asks for Contents write and Administration write.

## What Changes
- The permission set of the drift Job gets `contents: write` and `administration: write`. Each other permission stays `read`.
- The set, the setting and its variable are no longer read-only, so they get the name of what they are: `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS`, `service.github_app.drift_check` and `DEVOPS_CLI_SERVICE_GITHUB_APP_DRIFT_CHECK`. CronJob `repos-drift` sets the new variable.
- The Job also runs row 4 (Code Quality): its GET needs Administration write, which was the only reason to leave it out. A 404 makes the row `not available`, which is no drift and no failed read.
- Plan mode still sends GET requests only. A test runs the drift check with the new token over a repository off its baseline and proves that each request other than the token request is a GET.
- The token request, the setting, its variable and the manifest are observable, so the change carries spec deltas.
- The change fits one pull request.

## Capabilities
- `github-app-identity`: REMOVED requirement "A read-only process asks for read permissions only", and ADDED requirement "The drift check asks for its own permissions", because each scenario gets a new name.
- `repos-drift-alerts`: RENAMED and MODIFIED requirement "A nightly Job runs the drift check with a read-only identity", to "A nightly Job runs the drift check as the App". The Purpose of the capability drops "read-only".

## Impact
- Rows 2 and 10 of the drift Job read the merge settings and the bypass actors, so `RepositorySettingsUnreadable` stops for them, and `RepositorySettingsDrift` fires on a real difference.
- The token of the pod can write the contents and the settings of each repository of the installation. The pod already holds the key of the App, which can mint a token with each permission of the installation, so the read-only request guarded only against a bug of the code (owner comment of the decision). The writer of the command sends no write in a plan (`RouteWriter`, `confirm=False`), and the new test proves it.
- The installation must grant Contents write and Administration write. The App of the owner has read and write on each repository permission (docs/CLUSTER.md, step 1).
- The docs, the manifest comment, the alert text and the Status History of ADR 0015 state the new set.

## Feasibility
- GitHub REST documentation, "Get a repository" (read 2026-11-23): "To view merge-related settings, you must have the contents:read and contents:write permissions."
- GitHub REST documentation, "Get a repository ruleset" (read 2026-11-23): "the bypass_actors property is only returned if the user making the API request has write access to the ruleset." "Permissions required for GitHub Apps" lists `PUT /repos/{owner}/{repo}/rulesets/{ruleset_id}` and `GET /repos/{owner}/{repo}/code-quality/setup` under Administration write.
- Code: `configured_app` in `src/devops_cli/github/app_installation.py` gives `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS` when `read_only` is true, and `RouteWriter.rest` in `src/devops_cli/github/onboard/routes.py` records a write and sends nothing when `confirm` is false.
- Rename census: `git grep -l "READ_TOKEN_PERMISSIONS\|GITHUB_APP_READ_ONLY\|github_app\.read_only" -- ':!openspec/changes' ':!CHANGELOG.md' ':!docs/agent/archive'` on origin/main `4f707a4e0` gives 14 files. `src/devops_cli/k8s/configmap.py`, `tests/k8s/test_k8s_configmap.py` and the generated `docs/CONFIGURATION.md` name the field `read_only` alone, so the set is 17 files: 4 under `src/`, 4 tests, 1 manifest, 6 documents and 2 specs. Each changes in this pull request. The alert text of `RepositorySettingsUnreadable` and its promtool fixture say "the read-only token", and they change too.
- Settings ignore an unknown variable of the prefix: `load_settings()` with `DEVOPS_CLI_SERVICE_GITHUB_APP_NO_SUCH_FIELD=true` loads. So a pod with the old variable and the new image does not stop.

## Existing Tool Considered
- GitHub decides which fields a token gets, and the App token request already exists (`mint_installation_token`, gidgethub). The change edits one constant and renames one setting; no tool replaces it.
- Build cost: about 20 lines of code and 2 tests; about 60k tokens and 1 hour, most of it in the documents.
- The change deletes the setting `read_only` and the constant `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS`.
