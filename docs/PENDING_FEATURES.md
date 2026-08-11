# Pending Features & Design Proposals — devops-cli

Tracks active feature proposals, architectural spikes, and planned functionality.

---

## 1. Line-Level GitHub Pull Request Inline Comments
- **Overview**: Map `Finding.location` (e.g. `src/config.py:72-85`) to GitHub PR diff Hunk position offsets via PyGithub/GraphQL to post findings directly inline on PR Files Changed views.
- **Deduplication**: Prevent re-posting duplicate inline comments across re-runs on the same commit SHA.

---

## 2. Human Invalidation Feedback Loop for Prompt Tuning
- **Overview**: Export invalidated findings (`status="INVALIDATED"`) recorded via `devops review verify` into benchmark datasets (`devops review export-feedback`) to refine persona prompt instructions and few-shot examples.

---

## 3. Custom Team Persona Definitions
- **Overview**: Support repository-level persona definitions under `.devops/personas/<name>.md`, dynamically loaded during `devops review path|branch|pr --persona <custom_name>`.

---

## 4. Keyring Fallback & Headless Environment Auth
- **Overview**: Provide `devops config auth-headless` to securely load session tokens into ephemeral memory for headless Linux CI runners lacking DBus / SecretService.

---

## 5. Feature Prioritization & Implementation ROI

| Feature Proposal | Priority Tier | Value | Effort | ROI & Sequencing |
|---|---|---|---|---|
| **1. Line-Level PR Inline Comments** | **P1 (Highest)** | High | High | **High Impact**: Anchors persona findings directly to PR diff lines via PyGithub. |
| **2. Invalidation Feedback Exporter** | **P1 (High)** | High | Medium | **High Impact**: Exports false-positive datasets for continuous prompt tuning. |
| **3. Custom Team Persona Prompts** | **P2 (Medium)** | High | Medium | **Medium Impact**: Enables team-specific governance overlays (`.devops/personas/`). |
| **4. Headless Keyring Auth Fallback** | **P3 (Lower)** | Medium | Medium | **Niche Impact**: Unlocks headless CI runners without DBus. |
