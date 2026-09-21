# Task 346: Add Claude CLI and VS Code Extension to DevContainer Configuration & Lifecycle

**Issue**: [#346](https://github.com/dan-petty/devops-cli/issues/346)
**PR**: Tracking PR targeting `release/v0.2.22`
**Status**: Completed
**Milestone**: `v0.2.22`
**Priority**: `priority/p2-medium`
**Scope**: `type/infra`, `priority/p2-medium`

---

## 1. Description & Objectives

Integrate Anthropic Claude Code CLI and the official Claude VS Code extension (`anthropic.claude-code`) into the DevOps CLI devcontainer ecosystem. This ensures developers and AI agents operating within devcontainers have immediate, automated access to Claude Code workflows and editor features.

#### Key Deliverables:
- [x] **DevContainer Configuration & Feature**:
  - Added `ghcr.io/anthropics/devcontainer-features/claude-code:1` to `.devcontainer/devcontainer.json`.
  - Added feature lock entry to `.devcontainer/devcontainer-lock.json` with pinned sha256 digest (`cfc2e7d3e9fd3b9b01f8d5cb158508a884c8c0ede2e23ed10f32dea5d4ffe69a`).
  - Added `CONST_DEVCONTAINER_CLAUDE_EXTENSION` and `CONST_DEVCONTAINER_CLAUDE_FEATURE` constants to `src/devops_cli/config/constants.py` and exported them in `config/__init__.py`.
- [x] **VS Code & Antigravity Extensions**:
  - Added `anthropic.claude-code` to `customizations.vscode.extensions` and `customizations.antigravity.extensions` in `.devcontainer/devcontainer.json`.
  - Added `anthropic.claude-code` and feature definition to `src/devops_cli/templates/devcontainer.json.j2`.
- [x] **Native Post-Create Lifecycle Bootstrapping**:
  - Extracted modular `_bootstrap_developer_tools` in `src/devops_cli/commands/devcontainer.py`.
  - Added automated bootstrapping for standalone `claude` CLI (`curl -fsSL https://claude.ai/install.sh | bash`) alongside `uv` and `pre-commit` if missing in `$HOME/.local/bin`.
- [x] **Unit Testing & Invariants**:
  - Added unit tests in `tests/test_devcontainer.py` verifying `claude` CLI bootstrapping during `post-create` and error warning handling.
  - Added unit test verifying `init` scaffolds `anthropic.claude-code` extension and `claude-code:1` feature.
  - 100% compliance with Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Summary

- **Pytest**: 42/42 passed in `tests/test_devcontainer.py`.
- **Architectural Invariants**: Complexity check passed ($M \le 10$, depth $\le 5$ for all new helpers and tests).
- **Gated CI Quality Gates**: All 10 gates passed locally via `uv run devops ci`.
