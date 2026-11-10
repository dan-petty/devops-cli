# Tasks

## 1. Repository configuration

- [x] 1.1 Turn off AI Scan for pull requests via GitHub API
  - Verification: `$ uv run devops gh api repos/dan-petty/devops-cli/code-scanning/ai-scan`

## 2. Documents

- [x] 2.1 Update ADR 0004 decision D6 with AI Scan setting and read-back commands
  - Verification: `$ uv run devops docs check`
- [x] 2.2 Verify OpenSpec change validity
  - Verification: `$ uv run devops openspec check`

## Criteria

- Group 1: AI Scan for pull requests is disabled in repository settings.
- Group 2: ADR 0004 records the setting and its read-back command, and documentation checks pass.
