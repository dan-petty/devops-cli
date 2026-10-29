# Proposal

## Why

Issue #2000: Argo CD's GitHub notifier needs a GitHub App ID, an installation ID and a private key, and no setting, keyring entry or cluster Secret holds them. A notification service that fails to build stops every notification of the controller, so the Secret must hold these values before the notifier configuration (#1393) merges.

## What Changes

- `ArgoCDConfig` gets two plain settings, `argocd.github_app_id` and `argocd.github_app_installation_id` (variables `DEVOPS_CLI_ARGOCD_GITHUB_APP_ID` and `DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID`). Neither ID is a credential.
- The managed credential `argocd.github_app_private_key` (keyring `argocd_github_app_private_key`) holds the App's PEM private key. A person stores it with `devops config set argocd.github_app_private_key --from-file <key.pem>` (#1962).
- The cluster Secret table gets row `argocd/argocd-notifications-secret` (stack `infra`, no restart) with three optional entries: `github-appID` and `github-installationID` from the settings, and `github-privateKey` from the keyring with no generator. These are the keys that the notifier's `service.github` refers to as `$github-appID`, `$github-installationID` and `$github-privateKey`.
- A setting with no value now names `devops config set <key>` in the push's warning, as a keyring entry already does.
- `k8s/argocd/values.yaml` sets `notifications.secret.create: false`, so the push is the one owner of the Secret when #1393 turns notifications on. The `homelab` AppProject ignores the pushed Secret as an orphan, as it does for the other pushed Secrets.
- The settings, the credential and the push row are observable, so the change carries a delta in `stack-credential-sync`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `stack-credential-sync`: the push writes Argo CD's notifier Secret from two settings and one keyring entry, and the Argo CD chart creates no Secret of the same name.

## Impact

- `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`, `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/k8s/secret_push.py`.
- `k8s/argocd/values.yaml`, `k8s/argocd/apps/projects.yaml`, `k8s/README.md`.
- `tests/test_k8s_push_secrets.py`, `tests/test_k8s_argocd_apps.py`, `tests/test_config_declarations.py`.
- `docs/CONFIGURATION.md` and `docs/ENV_VARS.md`, which `devops docs generate --sync-readme` rewrites.

## Feasibility

- Argo CD v3.2.0, `docs/operator-manual/notifications/services/github.md`: the GitHub service reads `appID`, `installationID` and `privateKey` (and an optional `enterpriseBaseURL`). Its example stores the key as `github-privateKey` in `argocd-notifications-secret` and refers to it as `$github-privateKey`. `notifications/services/overview.md` ("Sensitive Data"): any service field can refer to a key of that Secret with `$<secret-key>`, so the two IDs can come from the Secret too and stay out of git.
- Chart `argo-cd` 10.9.6, the pinned version (`helm show values argo-cd --repo https://argoproj.github.io/argo-helm --version 10.9.6`): `notifications.enabled` defaults to true and `notifications.secret.create` to true, with name `argocd-notifications-secret` and empty `items`. `k8s/argocd/values.yaml` sets `notifications.enabled: false`, so the chart renders no such Secret now. If #1393 turns notifications on with the default `secret.create`, Argo CD (prune and selfHeal) and the push would both own the Secret. `secret.create: false` prevents that.
- Live cluster (2026-10-29, read-only): namespace `argocd` exists and holds no `argocd-notifications-secret`.
- `src/devops_cli/k8s/secret_push.py` already resolves `SettingSource` entries (`_setting`, `dotted_get` over the loaded settings) and writes `type: Opaque`, the type of Argo CD's own notifications Secret. So the row needs no new push code and no Secret type per row (#2008).
- A push leaves out a Secret whose namespace does not exist (`_present`), so a cluster without Argo CD skips the row.
- The issue's references to `config/options.py` and `KEYRING_KEYS` are stale: #2444 moved the declarations onto the settings fields (`Variable()`) and `CREDENTIALS` in `config/env.py`. The change uses those.
- #1647 (closed) gave the roadmap Service its own App (`service.github_app.*`). The notifier gets a separate App and separate settings, as the issue says: the notifier needs only deployment and status permissions, and keeping the two Apps apart keeps each one's permissions small.

## Existing Tool Considered

Argo CD's notifications engine and its documented `argocd-notifications-secret` keys are the tool; the change only feeds them. The cluster Secret push (`devops k8s push-secrets`) already reads keyring and setting sources, so the change adds settings, one credential and one table row, and builds no push or auth code. It deletes nothing.
