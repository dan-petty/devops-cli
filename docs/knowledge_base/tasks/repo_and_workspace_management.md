# Knowledge Base Task: Repository & Multi-Root Workspace Management

## 1. Overview & Purpose

Repository and multi-root workspace management in `devops-cli` provides automated organization-wide Git repository cloning, workspace synchronization, VS Code multi-root `.code-workspace` generation, and branch hygiene enforcement across complex multi-repo developer environments.

---

## 2. Architecture & Workspace Structure

```text
/workspaces/devops-cli/
├── src/devops_cli/         # Primary devops-cli codebase
├── repos/                  # Child multi-repo root
│   └── dan-petty/
│       ├── gdot-local-dev/ # Cloned child repo
│       └── ...
├── .code-workspace         # VS Code multi-root workspace definition
└── .data/                  # Local state, vector stores, and cache
```

- **Dynamic Org Cloning**: `devops repos clone-org <org>` fetches repository lists from GitHub API and clones them concurrently under `repos/<org>/`.
- **Workspace Synchronization**: `devops workspace sync` walks `repos/` (bounded 2 levels) and updates the root `.code-workspace` JSON file, registering all child projects automatically.
- **Git Status Matrix**: `devops repos status` scans all repositories and presents a rich terminal table showing active branches, uncommitted changes, and ahead/behind commit counts.

---

## 3. Useful Usage Information & Common Commands

### Workspace & Repository Commands
```bash
# Clone all repositories from a GitHub organization into repos/<org>/
devops repos clone-org dan-petty

# Display status of all cloned repositories (branch, modified files, unpushed commits)
devops repos status

# Synchronize all repositories with remote upstream (fetch & pull)
devops repos sync

# Synchronize VS Code multi-root workspace configuration (.code-workspace)
devops workspace sync

# List all discovered workspaces and their metadata
devops workspace list
```

---

## 4. Best Practice Guidance

1. **Keep Child Repos Isolated**: Child projects must remain independent Git repositories with their own `pyproject.toml`, `uv.lock`, and `AGENTS.md`.
2. **Use Bounded Directory Traversal**: When discovering projects, avoid scanning through `.venv/`, `.git/`, or `node_modules/`.
3. **Commit Cleanliness**: Run `devops repos status` before switching tasks to ensure no uncommitted files or unpushed branches are forgotten.
4. **Target Path Resolution**: All AI review, linting, and scanning operations must resolve paths relative to the specific target project root.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Git Credential Isolation**: Authenticate Git operations via SSH agent or OS Keyring tokens; never embed credentials in `.git/config` URLs.
- **Path Traversal Protection**: Guard workspace discovery operations against symlink attacks and escaping the root workspace directory.

---

## 6. General Standards & Reference Guidelines

- **Child Repo Directory**: `repos/<org>/<repo-name>`.
- **Workspace File**: Root `.code-workspace` JSON file formatted with 2-space indentation.
