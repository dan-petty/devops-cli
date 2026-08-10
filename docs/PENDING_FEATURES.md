# Pending Features & Design Proposals — devops-cli

This document tracks active feature proposals, architectural spikes, and planned functionality for upcoming releases.

---

## 1. Line-Level GitHub Pull Request Inline Comments

### Overview
Currently, `devops review pr <number> --post` posts the consolidated multi-persona review as a single top-level issue comment on the PR.

### Proposed Behavior
- Parse file paths and line ranges from `Finding.location` (e.g. `src/devops_cli/config.py:72-85`).
- Query PR diff Hunks via GitHub API to map source line numbers to position offsets within the PR diff.
- Submit review comments via `pull.create_review(commit=..., comments=[...])` so findings appear inline in the GitHub PR Files Changed view.

### Open Design Questions
- **Duplicate Suppression**: Avoid re-posting inline comments for findings that were already posted in previous review runs on the same commit SHA.

---

## 2. Human Invalidation Feedback Loop for Prompt Optimization

### Overview
When a persona generates a false positive or unverified finding, engineers use `devops review verify <session_id> --index N --status invalidated --reason "Explanation"` to mark it as invalidated.

### Proposed Behavior
- Store human invalidating feedback reasons in `.data/reviews/<session_id>/findings.json`.
- Provide `devops review export-feedback [--out feedback.json]` to bundle invalidated findings across sessions.
- Ingest feedback datasets during persona prompt development (`ai/personas/_shared/compose.md` and individual persona prompts) to refine few-shot examples and verification rules.

---

## 3. Custom Team Persona Definitions

### Overview
Currently, personas (`devsecops`, `architect`, `pm`, `auditor`, `qa`) are defined statically in `src/devops_cli/ai/personas/`.

### Proposed Behavior
- Allow repositories to define custom persona markdown prompts under `.devops/personas/<name>.md`.
- Register custom personas dynamically during `devops review path|branch|pr --persona <custom_name>`.

---

## 4. Keyring Fallback & Headless Environment Authentication

### Overview
`devops-cli` strictly stores secret tokens in the OS keyring. In headless Linux CI environments where DBus / SecretService is unavailable, `keyring` falls back to `SecretStorageError`.

### Proposed Behavior
- Provide `devops config auth-headless` to securely load session tokens from encrypted ephemeral memory without committing to environment variables or plaintext files.

---

## 5. Feature Prioritization & Implementation ROI

| Feature Proposal | Priority Tier | Value | Effort | Implementation ROI & Sequencing |
|---|---|---|---|---|
| **1. Line-Level PR Inline Comments** | **P1 (Highest)** | High | High | **High Impact**: Transforms PR review UX by anchoring persona findings directly to file lines. Implementation requires diff hunk position mapping via PyGithub. |
| **2. Invalidation Feedback Exporter** | **P1 (High)** | High | Medium | **High Impact**: Unlocks continuous prompt optimization by exporting human-verified false positive datasets for prompt tuning. |
| **3. Custom Team Persona Prompts** | **P2 (Medium)** | High | Medium | **Medium Impact**: Enables team-specific governance overlays (`.devops/personas/`). Lower complexity since persona loading is isolated. |
| **4. Headless Keyring Auth Fallback** | **P3 (Lower)** | Medium | Medium | **Niche Impact**: Only needed in headless CI runners without DBus. Local workstation usage is already 100% covered. |

