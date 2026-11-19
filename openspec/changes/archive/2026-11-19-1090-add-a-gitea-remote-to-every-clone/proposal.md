# Proposal: #1090

## Why

Every git repository under `repos/` has only one remote, `origin` on GitHub. Gitea is the internal forge for iteration branches that do not need to go to GitHub before review. Without Gitea remotes and credential helpers, developers and automated agents cannot push iteration branches to the internal forge. Closes #1090.

## What Changes

- Add settings `gitea.url`, `gitea.username`, `gitea.github_branches`, and `gitea.extra_checkouts` to configuration.
- Add managed credential `gitea.token` in `CREDENTIALS`.
- Add a typed Gitea API client in `src/devops_cli/gitea/client.py` using `httpx2`.
- Add `devops repos gitea connect` to discover or set Gitea URL, check credentials, and store settings.
- Add `devops repos remotes` to create missing organizations, repositories, and branch protections on Gitea, set remotes and credential helpers, and seed default branches.
- Add hidden `devops repos gitea credential get|store|erase` as a git credential helper.
- Update `devops repos sync` to fetch both remotes and carry default branches over to Gitea without forcing.
- Update `devops repos clone` and `clone-org` to run the Gitea remote ensure step when `gitea.url` is set.

## Capabilities

- `gitea-remotes`: Configures, manages, and synchronizes Gitea remotes across workspace clones.

## Impact

- Clones under `repos/` and extra checkouts gain a `gitea` remote and URL-scoped credential helper.
- `devops repos sync` updates Gitea default branches automatically.
- No impact on external GitHub remotes or existing Git workflows.

## Feasibility

- Tested against Gitea API specifications and local subprocess git runner.
- All network interactions use `MockTransport` during automated testing.
- No real Git daemon or network connections required during CI.

## Existing Tool Considered

The official `tea` CLI (v0.16.0) lacks branch-protection commands and stores tokens in plain text in config files instead of the system keyring. Gitea has no official Python SDK (official SDK is Go). A lightweight internal client on top of existing `httpx2` avoids unsafe token storage and covers the exact required endpoints.
