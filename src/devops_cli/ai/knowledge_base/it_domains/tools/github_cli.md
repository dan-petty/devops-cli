---
applies_to:
  - "tool:gh@2.*"
sources:
  - "https://cli.github.com/"
  - "https://github.com/cli/cli"
reviewed: "2026-10-15"
tags:
  - "gh"
  - "github"
---

# Knowledge Base: GitHub CLI (gh) (VCS & Remote Automation)

## 1. Overview & Purpose

The GitHub CLI (`gh`) brings GitHub pull requests, issues, Actions workflows, releases, and repository configuration directly to the command line. In the `devops-cli` ecosystem, `gh` powers pull request creation (`devops pr create`), remote GitHub Actions CI check monitoring, organization repository discovery, and branch synchronization.

---

## 2. Usage Information & Architecture

- **Token Authentication**: One GitHub identity per process: on the first GitHub call `gh auth token` runs once (it applies `GH_TOKEN`, then `GITHUB_TOKEN`, then gh's stored login), and every gh and git child gets that token as `GH_TOKEN`. `gh auth` subcommands are exempt and see the environment unchanged. In the cluster, a process whose environment holds `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` acts as GitHub App `devops-cli-service` instead: it mints an installation token, mints a new one before the token expires, and gives the current token to each gh and git child as `GH_TOKEN` (ADR 0015).
- **API Client**: Programmatic interaction via `src/devops_cli/github/client.py` and rate-managed CLI invocation via `run_gh([CONST_GH_CLI, ...])`.
- **Active Monitoring**: When creating or updating PRs, DevOps CLI actively polls and verifies remote GitHub Actions check runs.
- **CLI Subcommands**: `devops pr`, `devops gh` and `devops repos` commands wrap GitHub operations.

---

## 3. Common & Advanced Commands

### DevOps CLI GitHub Workflows
```bash
# View active pull request status and check runs
devops pr view 17

# Clone all repositories from a GitHub organization
devops repos clone-org dan-petty
```

### Standard & Advanced `gh` CLI Commands
```bash
# Authenticate GitHub CLI interactively; gh keeps the token in its own credential store
gh auth login

# Check authentication and token scopes
gh auth status

# Create a draft pull request into main (devops pr create always opens a draft)
devops pr create --title "feat(serve): FastAPI service engine" \
  --body "Implements FastAPI service engine with OpenAPI docs."

# Mark the draft ready for review once its checks pass
devops pr ready 17

# Watch GitHub Actions CI checks for a pull request in real-time
devops pr monitor 17

# List recent workflow runs on a specific branch
devops gh runs list --branch main --limit 5

# View failure logs for a specific GitHub Actions workflow run
devops gh runs view <run_id> --log-failed

# Read a release and its assets through the rate-managed client
devops gh api repos/<owner>/<repo>/releases/tags/<tag>
```

---

## 4. Best Practice Guidance

1. **Target the Default Branch**: PRs for features and bug fixes target `main`. release-please opens the only release PR, and a person merges it.
2. **Monitor Remote CI to Green**: Never submit a PR without actively monitoring remote CI checks (`devops pr monitor <pr>`) until all checks pass.
3. **Structured PR Titles**: Follow Conventional Commits format in PR titles (`feat(scope): ...`, `fix(scope): ...`). The squash commit takes the title, and release-please writes it as the changelog line.
4. **Fine-Grained Permissions**: Use fine-grained GitHub Personal Access Tokens scoped to specific repositories with minimal required permissions (`Contents: Read/Write`, `Pull Requests: Read/Write`, `Workflows: Read`).

---

## 5. Security Recommendations & Zero-Trust Policies

- **Never Print Tokens in Logs**: Tokens must never be logged or echoed in shell traces.
- **Keyring Storage**: Log in with `gh auth login`; gh keeps the token in the system keyring, and devops-cli keeps no copy of it.
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
- **DevOps CLI GitHub Client**: [src/devops_cli/github/client.py](../../../../github/client.py)
