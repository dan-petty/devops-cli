# Design

## Decisions

- **Branch ownership model**: GitHub owns each repository default branch (`main`), tags, pull requests, CI, and releases. Gitea owns iteration branches. `devops repos sync` fast-forwards Gitea default branch from `origin` without forcing.
- **Git execution**: Git commands run via `run_subprocess` through the process runner. Tests use `git_fake` and test transcripts without invoking real git.
- **Credential management**: `gitea.token` is declared in `CREDENTIALS` in `src/devops_cli/config/env.py`. Keyring name is `gitea_token` and environment variable is `DEVOPS_CLI_GITEA_TOKEN`. Hidden input is used when prompted via `devops config set gitea.token`.
- **Gitea API Client**: Built on `httpx2` client using `configured_level()`. Does not follow redirects (`follow_redirects=False`) to detect Cloudflare Access blocks. Any redirect to a different host or 403 with `cf-mitigated: challenge` raises `GiteaAccessBlocked`.
- **Credential helper**: Implemented as hidden CLI command `devops repos gitea credential get|store|erase`. Reads `protocol=https` and matching host from stdin, returns username and password from keyring, performs zero network calls.
- **Branch synchronization**: `devops repos sync` fetches both `origin` and `gitea` remotes. It pushes default branch and patterns in `gitea.github_branches` using `git push --porcelain`. Porcelain lines are parsed (`*` success, `!` rejected non-fast-forward).

## Rejected alternatives

- **Gitea pull mirror**: Pull mirrors are read-only and refuse pushes, preventing iteration branches on Gitea.
- **Gitea push mirror**: Push mirrors force-push all refs, risking overwriting GitHub merges.
- **In-cluster sync job**: Introduces an unnecessary new component with separate GitHub credentials in cluster.
- **tea CLI**: Plain-text token storage violates security requirements for keyring storage.
- **Dual writes to both forges**: Adds dual writers without safety guarantees.
