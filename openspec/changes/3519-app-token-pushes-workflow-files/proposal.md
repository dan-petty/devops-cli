# Proposal

## Why

Issue #3519: GitHub refuses a push from the implement job when the branch changes a file under `.github/workflows/`, with the text `refusing to allow a GitHub App to create or update workflow`. A retry cannot change this refusal. On a target repository, an item whose plan changes a workflow file cannot deliver. GitHub App `devops-cli-service` holds read and write on all repository permissions, but `CONST_GITHUB_APP_TOKEN_PERMISSIONS` leaves out `workflows`, so no token can push a workflow file. On 2026-11-04 the owner chose to add the permission to every token.

## What Changes

- `CONST_GITHUB_APP_TOKEN_PERMISSIONS` gives `workflows` the level `write`, so each token request, the log of a minted token and the HTTP 422 message name it.
- ADR 0015 and `k8s/README.md` state the new list and the risk: a workflow on a pushed branch can run with the secrets of the repository before a person reviews it.
- The change alters the request that the Service and the cluster Jobs send to GitHub and an error message, so it carries a spec delta: three MODIFIED requirements in `github-app-identity`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `github-app-identity`: each installation token also asks for `workflows: write`.

## Impact

- `src/devops_cli/config/constants.py`.
- `tests/github/test_github_app_identity.py`.
- `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`, `k8s/README.md`.

## Feasibility

- The GitHub REST documentation of "Create an installation access token for an app" gives the body parameter `permissions.workflows` the description "The level of permission to grant the access token to update GitHub Actions workflow files", and `write` is its only value.
- The owner read the settings of the App on 2026-11-04: it holds read and write on all repository permissions, so the installation grants the new permission and GitHub does not refuse the token with HTTP 422.
- Comments on an item of a target repository quote the refusal from `git push`.

## Existing Tool Considered

The change sets one value in a request to the GitHub REST API. It adds no tool and no code path.
