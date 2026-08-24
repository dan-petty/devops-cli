# Knowledge Base: GitHub CLI (gh) (VCS & Remote Automation)

## 1. Overview & Purpose

The GitHub CLI (`gh`) brings GitHub pull requests, issues, Actions workflows, releases, and repository configuration directly to the command line. In the `devops-cli` ecosystem, `gh` powers release PR creation (`devops release create-pr`), remote GitHub Actions CI check monitoring, organization repository discovery, and branch synchronization.

---

## 2. Usage Information & Architecture

- **Token Authentication**: Leverages GitHub Personal Access Tokens (classic or fine-grained) or OAuth tokens securely resolved from OS Keyring (`devops config get github.token`) or environment variable `DEVOPS_CLI_GITHUB_TOKEN`.
- **API Client**: Programmatic interaction via `src/devops_cli/github/client.py` and direct CLI invocation via `run_subprocess(["gh", ...])`.
- **Active Monitoring**: When creating or updating PRs, DevOps CLI actively polls and verifies remote GitHub Actions check runs.
- **CLI Subcommands**: `devops pr`, `devops repos`, and `devops release` commands wrap GitHub operations.

---

## 3. Common & Advanced Commands

### DevOps CLI GitHub Workflows
```bash
# View active pull request status and check runs
devops pr view 17

# Create official release PR targeting main
devops release create-pr --version 0.2.0

# Clone all repositories from a GitHub organization
devops repos clone-org dan-petty
```

### Standard & Advanced `gh` CLI Commands
```bash
# Authenticate GitHub CLI with token from standard input
echo "$GITHUB_TOKEN" | gh auth login --with-token

# Check authentication and token scopes
gh auth status

# Create a pull request targeting a specific base branch
gh pr create --title "feat(serve): FastAPI service engine" \
  --body "Implements FastAPI service engine with OpenAPI docs." \
  --base release/v0.2.0 \
  --head feat/serve-engine

# Watch GitHub Actions CI checks for a pull request in real-time
gh pr checks 17 --watch

# List recent workflow runs on a specific branch
gh run list --branch release/v0.2.0 -L 5

# View failure logs for a specific GitHub Actions workflow run
gh run view <run_id> --log-failed

# Download release assets
gh release download v0.2.0 --pattern "*.tar.gz"
```

---

## 4. Best Practice Guidance

1. **Target Base Branch Explicitly**: When creating PRs for features or bug fixes, always target active release branches (`--base release/v<version>`). Release PRs target `main`.
2. **Monitor Remote CI to Green**: Never submit a PR without actively monitoring remote CI checks (`gh pr checks <pr> --watch`) until all checks pass.
3. **Structured PR Titles**: Follow Conventional Commits format in PR titles (`feat(scope): ...`, `fix(scope): ...`).
4. **Fine-Grained Permissions**: Use fine-grained GitHub Personal Access Tokens scoped to specific repositories with minimal required permissions (`Contents: Read/Write`, `Pull Requests: Read/Write`, `Workflows: Read`).

---

## 5. Security Recommendations & Zero-Trust Policies

- **Never Print Tokens in Logs**: Tokens must never be logged or echoed in shell traces.
- **Keyring Storage**: Always store GitHub tokens in the OS Keyring using `devops config set github.token <token>`.
- **Human-in-the-Loop Governance**: AI agents prepare PRs and monitor checks, but merging into protected branches requires maintainer approval.

---

## 6. General Standards & Reference Guidelines

- **Default Remote**: Standard Git remote name is `origin`.
- **API Version**: Target GitHub REST API v3 / GraphQL API with modern HTTP/2 clients.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [cli.github.com](https://cli.github.com/)
- **Public Git Repository**: [github.com/cli/cli](https://github.com/cli/cli)
- **DevOps CLI Repository**: [github.com/dan-petty/devops-cli](https://github.com/dan-petty/devops-cli)
- **DevOps CLI GitHub Client**: [src/devops_cli/github/client.py](../../../github/client.py)
